import { Injectable } from '@nestjs/common';
import { lookup } from 'node:dns/promises';
import { isIP } from 'node:net';
import { DatabaseService } from '../database/database.service';

const DEFAULT_ALLOWED_HOSTS = ['raw.githubusercontent.com', 'github.com', 'medium.com'];
const DEFAULT_CACHE_TTL_SECONDS = 3600;
const DEFAULT_FETCH_TIMEOUT_MS = 10000;
const DEFAULT_MAX_BYTES = 1024 * 1024;
const DEFAULT_MAX_CACHE_ROWS = 1000;
const MAX_CONFIGURED_FETCH_TIMEOUT_MS = 120000;
const MAX_CONFIGURED_BYTES = 10 * 1024 * 1024;
const MAX_CONFIGURED_CACHE_ROWS = 100000;
const MAX_TITLE_LENGTH = 200;
const MAX_URL_LENGTH = 2048;

export interface WebReferenceResult {
  url: string;
  statusCode: number;
  contentType: string | null;
  title: string | null;
  body: string;
  fetchedAt: string;
  expiresAt: string;
  cached: boolean;
  error?: string;
}
export class WebReferenceValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'WebReferenceValidationError';
  }
}


interface WebReferenceRow {
  url: string;
  status_code: number;
  content_type: string | null;
  title: string | null;
  body: string;
  fetched_at: Date | string;
  expires_at: Date | string;
  metadata: Record<string, unknown> | null;
}

interface FetchedResponse {
  statusCode: number;
  contentType: string | null;
  title: string | null;
  body: string;
  error?: string;
}

@Injectable()
export class WebReferenceService {
  private readonly allowedHosts: string[];
  private readonly cacheTtlSeconds: number;
  private readonly fetchTimeoutMs: number;
  private readonly maxBytes: number;
  private readonly maxCacheRows: number;

  constructor(private readonly database: DatabaseService) {
    this.allowedHosts = this.readAllowedHosts();
    this.cacheTtlSeconds = this.readPositiveNumber('WEB_CACHE_TTL_SECONDS', DEFAULT_CACHE_TTL_SECONDS);
    this.fetchTimeoutMs = this.readPositiveNumber(
      'WEB_FETCH_TIMEOUT_MS',
      DEFAULT_FETCH_TIMEOUT_MS,
      MAX_CONFIGURED_FETCH_TIMEOUT_MS,
    );
    this.maxBytes = this.readPositiveNumber('WEB_MAX_BYTES', DEFAULT_MAX_BYTES, MAX_CONFIGURED_BYTES);
    this.maxCacheRows = this.readPositiveNumber(
      'WEB_MAX_CACHE_ROWS',
      DEFAULT_MAX_CACHE_ROWS,
      MAX_CONFIGURED_CACHE_ROWS,
    );
  }

  async fetchReference(inputUrl: string): Promise<WebReferenceResult> {
    const url = this.validateUrl(inputUrl);
    const cached = await this.readCached(url);
    if (cached) {
      return { ...cached, cached: true };
    }

    const fetched = await this.fetchRemote(url);
    const now = new Date();
    const expiresAt = new Date(now.getTime() + this.cacheTtlSeconds * 1000);
    const metadata: Record<string, unknown> = fetched.error
      ? { error: fetched.error }
      : {};

    await this.database.query(
      `INSERT INTO web_references
        (url, status_code, content_type, title, body, fetched_at, expires_at, metadata)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
       ON CONFLICT (url) DO UPDATE SET
         status_code = EXCLUDED.status_code,
         content_type = EXCLUDED.content_type,
         title = EXCLUDED.title,
         body = EXCLUDED.body,
         fetched_at = EXCLUDED.fetched_at,
         expires_at = EXCLUDED.expires_at,
         metadata = EXCLUDED.metadata`,
      [
        url,
        fetched.statusCode,
        fetched.contentType,
        fetched.title,
        fetched.body,
        now,
        expiresAt,
        JSON.stringify(metadata),
      ],
    );
    await this.database.query('DELETE FROM web_references WHERE expires_at <= NOW()');
    await this.database.query(
      `DELETE FROM web_references
       WHERE url IN (
         SELECT url FROM web_references
         ORDER BY fetched_at DESC
         OFFSET $1
       )`,
      [this.maxCacheRows],
    );

    return {
      url,
      statusCode: fetched.statusCode,
      contentType: fetched.contentType,
      title: fetched.title,
      body: fetched.body,
      fetchedAt: now.toISOString(),
      expiresAt: expiresAt.toISOString(),
      cached: false,
      ...(fetched.error ? { error: fetched.error } : {}),
    };
  }

  private async readCached(url: string): Promise<Omit<WebReferenceResult, 'cached'> | null> {
    const result = await this.database.query<WebReferenceRow>(
      `SELECT url, status_code, content_type, title, body, fetched_at, expires_at, metadata
       FROM web_references
       WHERE url = $1 AND expires_at > NOW()
       LIMIT 1`,
      [url],
    );
    const row = result.rows[0];
    if (!row) {
      return null;
    }

    const metadata = row.metadata ?? {};
    const errorValue = metadata.error;
    return {
      url: row.url,
      statusCode: row.status_code,
      contentType: row.content_type,
      title: typeof row.title === 'string' ? row.title.slice(0, MAX_TITLE_LENGTH) : null,
      body: typeof row.body === 'string' ? this.boundText(row.body) : '',
      fetchedAt: this.toIsoString(row.fetched_at),
      expiresAt: this.toIsoString(row.expires_at),
      ...(typeof errorValue === 'string' ? { error: errorValue } : {}),
    };
  }

  private async fetchRemote(url: string): Promise<FetchedResponse> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.fetchTimeoutMs);
    try {
      await this.rejectUnsafeResolvedAddresses(url);
      const response = await fetch(url, {
        method: 'GET',
        redirect: 'error',
        signal: controller.signal,
        headers: {
          accept: 'text/html, text/plain, application/json;q=0.9, */*;q=0.1',
          'user-agent': 'memory/1.0',
        },
      });
      const contentType = response.headers.get('content-type');
      const bodyResult = await this.readBoundedBody(response);
      if (bodyResult.error) {
        return {
          statusCode: response.status,
          contentType,
          title: null,
          body: bodyResult.body,
          error: bodyResult.error,
        };
      }

      const title = this.extractTitle(bodyResult.body, contentType);
      const error = response.ok ? undefined : `Remote server returned HTTP ${response.status}.`;
      return {
        statusCode: response.status,
        contentType,
        title,
        body: bodyResult.body,
        ...(error ? { error } : {}),
      };
    } catch (error: unknown) {
      if (error instanceof WebReferenceValidationError) {
        throw error;
      }
      const message = error instanceof Error && error.name === 'AbortError'
        ? 'Remote request timed out.'
        : 'Unable to fetch remote reference.';
      return {
        statusCode: 0,
        contentType: null,
        title: null,
        body: message,
        error: message,
      };
    } finally {
      clearTimeout(timeout);
    }
  }

  private async rejectUnsafeResolvedAddresses(url: string): Promise<void> {
    const hostname = new URL(url).hostname.replace(/^\[|\]$/g, '');
    const addresses = await lookup(hostname, { all: true, verbatim: true });
    if (addresses.length === 0 || addresses.some(({ address }) => this.isLocalHost(address) || this.isPrivateIp(address))) {
      throw new WebReferenceValidationError('The URL host resolves to a local, private, or link-local address.');
    }
  }

  private async readBoundedBody(response: Response): Promise<{ body: string; error?: string }> {
    if (!response.body) {
      return { body: '' };
    }

    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let totalBytes = 0;
    try {
      while (true) {
        const next = await reader.read();
        if (next.done) {
          break;
        }
        const chunk = next.value;
        totalBytes += chunk.byteLength;
        if (totalBytes > this.maxBytes) {
          await reader.cancel();
          return {
            body: 'Remote response exceeded the configured size limit.',
            error: 'Remote response exceeded the configured size limit.',
          };
        }
        chunks.push(chunk);
      }
    } finally {
      reader.releaseLock();
    }

    const merged = new Uint8Array(totalBytes);
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return { body: new TextDecoder().decode(merged) };
  }

  private validateUrl(inputUrl: string): string {
    if (typeof inputUrl !== 'string' || inputUrl.length === 0 || inputUrl.length > MAX_URL_LENGTH) {
      throw new WebReferenceValidationError('URL must be a non-empty string no longer than 2048 characters.');
    }

    let parsed: URL;
    try {
      parsed = new URL(inputUrl);
    } catch {
      throw new WebReferenceValidationError('URL is invalid.');
    }

    const protocol = parsed.protocol.toLowerCase();
    if (protocol !== 'http:' && protocol !== 'https:') {
      throw new WebReferenceValidationError('Only http and https URLs are allowed.');
    }
    const authority = /^[a-z][a-z\d+.-]*:\/\/([^/?#]*)/i.exec(inputUrl.trim())?.[1] ?? '';
    if (parsed.username || parsed.password || authority.includes('@')) {
      throw new WebReferenceValidationError('URLs containing credentials are not allowed.');
    }

    const hostname = parsed.hostname.toLowerCase().replace(/\.$/, '');
    const hostnameForChecks = hostname.replace(/^\[|\]$/g, '');
    if (!hostnameForChecks || this.isLocalHost(hostnameForChecks) || this.isPrivateIp(hostnameForChecks)) {
      throw new WebReferenceValidationError('Local, private, and link-local hosts are not allowed.');
    }
    if (!this.allowedHosts.some((allowed) => hostnameForChecks === allowed || hostnameForChecks.endsWith(`.${allowed}`))) {
      throw new WebReferenceValidationError('The URL host is not allow-listed.');
    }

    parsed.hostname = hostname;
    return parsed.toString();
  }

  private readAllowedHosts(): string[] {
    const raw = process.env.WEB_ALLOWED_HOSTS;
    const values = (raw ?? '').split(',').map((value) => value.trim().toLowerCase().replace(/\.$/, '')).filter(Boolean);
    return values.length > 0 ? values : DEFAULT_ALLOWED_HOSTS;
  }

  private readPositiveNumber(name: string, fallback: number, maximum?: number): number {
    const parsed = Number(process.env[name]);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return fallback;
    }
    return Math.min(Math.floor(parsed), maximum ?? Number.MAX_SAFE_INTEGER);
  }

  private isLocalHost(hostname: string): boolean {
    return hostname === 'localhost'
      || hostname.endsWith('.localhost')
      || hostname === 'localhost.localdomain'
      || hostname === 'ip6-localhost';
  }

  private isPrivateIp(hostname: string): boolean {
    const ipVersion = isIP(hostname);
    if (ipVersion === 4) {
      const octets = hostname.split('.').map(Number);
      const [a, b, c] = octets;
      return a === 0 || a === 10 || a === 127 || (a === 169 && b === 254)
        || (a === 172 && b >= 16 && b <= 31)
        || (a === 192 && b === 168)
        || (a === 192 && b === 0 && c === 0)
        || (a === 100 && b >= 64 && b <= 127)
        || (a === 198 && b >= 18 && b <= 19)
        || a >= 224;
    }
    if (ipVersion !== 6) {
      return false;
    }

    const normalized = hostname.toLowerCase();
    if (normalized === '::' || normalized === '::1') {
      return true;
    }
    const mappedIpv4 = normalized.match(/^::ffff:(\d{1,3}(?:\.\d{1,3}){3})$/);
    if (mappedIpv4) {
      return this.isPrivateIp(mappedIpv4[1]);
    }
    const sections = normalized.split('::');
    if (sections.length <= 2) {
      const left = sections[0] ? sections[0].split(':').filter(Boolean) : [];
      const right = sections.length === 2 && sections[1] ? sections[1].split(':').filter(Boolean) : [];
      const missing = 8 - left.length - right.length;
      const groups = sections.length === 2
        ? [...left, ...Array(Math.max(0, missing)).fill('0'), ...right]
        : left;
      if (groups.length === 8) {
        const values = groups.map((group) => Number.parseInt(group, 16));
        if (values.slice(0, 5).every((value) => value === 0) && values[5] === 0xffff) {
          const mapped = `${values[6] >> 8}.${values[6] & 255}.${values[7] >> 8}.${values[7] & 255}`;
          return this.isPrivateIp(mapped);
        }
      }
    }
    const firstHextet = Number.parseInt(normalized.split(':')[0] || '0', 16);
    return (firstHextet & 0xfe00) === 0xfc00 || (firstHextet & 0xffc0) === 0xfe80;
  }
  private boundText(value: string): string {
    const bytes = new TextEncoder().encode(value);
    if (bytes.byteLength <= this.maxBytes) {
      return value;
    }
    return new TextDecoder().decode(bytes.slice(0, this.maxBytes));
  }


  private extractTitle(body: string, contentType: string | null): string | null {
    const looksLikeHtml = contentType?.toLowerCase().includes('html')
      || /^\s*(?:<!doctype\s+html\b|<html\b)/i.test(body);
    if (!looksLikeHtml) {
      return null;
    }
    const match = /<title(?:\s[^>]*)?>([\s\S]*?)<\/title>/i.exec(body);
    if (!match) {
      return null;
    }
    const title = this.decodeHtmlEntities(match[1].replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim());
    return title ? title.slice(0, MAX_TITLE_LENGTH) : null;
  }

  private decodeHtmlEntities(value: string): string {
    return value
      .replace(/&amp;/gi, '&')
      .replace(/&lt;/gi, '<')
      .replace(/&gt;/gi, '>')
      .replace(/&quot;/gi, '"')
      .replace(/&#39;|&apos;/gi, "'")
      .replace(/&#(\d+);/g, (_match, code: string) => {
        const numeric = Number(code);
        return Number.isInteger(numeric) && numeric >= 0 && numeric <= 0x10ffff
          ? String.fromCodePoint(numeric)
          : '';
      })
      .replace(/&#x([0-9a-f]+);/gi, (_match, code: string) => {
        const numeric = Number.parseInt(code, 16);
        return Number.isInteger(numeric) && numeric >= 0 && numeric <= 0x10ffff
          ? String.fromCodePoint(numeric)
          : '';
      });
  }

  private toIsoString(value: Date | string): string {
    return value instanceof Date ? value.toISOString() : new Date(value).toISOString();
  }
}

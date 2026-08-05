import { Injectable } from '@nestjs/common';
import { QueryResultRow } from 'pg';
import { DatabaseService } from '../database/database.service';

export interface WriteupSearchOptions {
  query?: string;
  domain?: string;
  difficulty?: string;
  limit?: number;
  offset?: number;
}

export interface WriteupSummary {
  id: number | string;
  sourceKey: string;
  challengeName: string;
  domain: string;
  difficulty: string;
  sourceRepo: string;
  sourceUrl: string | null;
  status: string;
  metadata: JsonValue;
  createdAt: string;
  updatedAt: string;
}

export interface WriteupRecord extends WriteupSummary {
  markdown: string;
}

export interface PagedResult<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

type JsonPrimitive = string | number | boolean | null;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 100;
const MAX_OFFSET = 100_000;

function boundedInteger(value: number | undefined, fallback: number, maximum?: number): number {
  if (value === undefined || !Number.isFinite(value)) {
    return fallback;
  }
  const integer = Math.floor(value);
  if (integer < 0) {
    return fallback;
  }
  return maximum === undefined ? integer : Math.min(integer, maximum);
}

function jsonSafe(value: unknown): JsonValue {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'bigint') {
    return value.toString();
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (Array.isArray(value)) {
    return value.map((item) => jsonSafe(item));
  }
  if (typeof value === 'object') {
    const output: { [key: string]: JsonValue } = {};
    for (const [key, item] of Object.entries(value)) {
      output[key] = jsonSafe(item);
    }
    return output;
  }
  return String(value);
}

function safeId(value: unknown): number | string {
  if (typeof value === 'number') {
    return Number.isSafeInteger(value) ? value : String(value);
  }
  if (typeof value === 'bigint') {
    return value <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(value) : value.toString();
  }
  const text = String(value);
  const numeric = Number(text);
  return Number.isSafeInteger(numeric) && text.trim() !== '' ? numeric : text;
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : String(value ?? '');
}

function dateValue(value: unknown): string {
  if (value instanceof Date) {
    return value.toISOString();
  }
  return String(value ?? '');
}

@Injectable()
export class WriteupsService {
  constructor(private readonly database: DatabaseService) {}

  async search(options: WriteupSearchOptions = {}): Promise<PagedResult<WriteupSummary>> {
    const limit = boundedInteger(options.limit, DEFAULT_LIMIT, MAX_LIMIT);
    const offset = boundedInteger(options.offset, 0, MAX_OFFSET);
    const clauses: string[] = [];
    const values: unknown[] = [];

    const query = options.query?.trim();
    if (query) {
      values.push(query);
      clauses.push(`search_vector @@ websearch_to_tsquery('simple', $${values.length})`);
    }
    const domain = options.domain?.trim();
    if (domain) {
      values.push(domain);
      clauses.push(`domain = $${values.length}`);
    }
    const difficulty = options.difficulty?.trim();
    if (difficulty) {
      values.push(difficulty);
      clauses.push(`difficulty = $${values.length}`);
    }

    const where = clauses.length > 0 ? `WHERE ${clauses.join(' AND ')}` : '';
    values.push(limit, offset);
    const limitPosition = values.length - 1;
    const offsetPosition = values.length;
    const result = await this.database.query<WriteupSummaryRow>(
      `SELECT id, source_key AS "sourceKey", challenge_name AS "challengeName", domain,
              difficulty, source_repo AS "sourceRepo", source_url AS "sourceUrl", status,
              metadata, created_at AS "createdAt", updated_at AS "updatedAt",
              COUNT(*) OVER() AS "totalCount"
         FROM writeups
         ${where}
        ORDER BY id ASC
        LIMIT $${limitPosition} OFFSET $${offsetPosition}`,
      values,
    );
    const items = result.rows.map((row) => this.toSummary(row));
    const firstTotal = result.rows[0]?.totalCount;
    const total = firstTotal === undefined ? result.rows.length : Number(firstTotal);
    return { items, total: Number.isFinite(total) ? total : 0, limit, offset };
  }

  async getById(id: number | string): Promise<WriteupRecord | null> {
    const numericId = this.numericId(id);
    if (numericId === null) {
      return null;
    }
    const result = await this.database.query<WriteupRow>(
      `SELECT id, source_key AS "sourceKey", challenge_name AS "challengeName", domain,
              difficulty, source_repo AS "sourceRepo", source_url AS "sourceUrl", status,
              markdown, metadata, created_at AS "createdAt", updated_at AS "updatedAt"
         FROM writeups
        WHERE id = $1
        LIMIT 1`,
      [numericId],
    );
    const row = result.rows[0];
    return row === undefined ? null : this.toRecord(row);
  }

  async getByChallengeName(challengeName: string): Promise<WriteupRecord | null> {
    const result = await this.database.query<WriteupRow>(
      `SELECT id, source_key AS "sourceKey", challenge_name AS "challengeName", domain,
              difficulty, source_repo AS "sourceRepo", source_url AS "sourceUrl", status,
              markdown, metadata, created_at AS "createdAt", updated_at AS "updatedAt"
         FROM writeups
        WHERE challenge_name = $1
        ORDER BY id ASC
        LIMIT 1`,
      [challengeName],
    );
    const row = result.rows[0];
    return row === undefined ? null : this.toRecord(row);
  }

  async listDomains(): Promise<Array<{ domain: string; count: number }>> {
    const result = await this.database.query<DomainRow>(
      `SELECT domain, COUNT(*) AS count
         FROM writeups
        GROUP BY domain
        ORDER BY domain ASC`,
    );
    return result.rows.map((row) => ({ domain: stringValue(row.domain), count: Number(row.count) }));
  }

  private numericId(id: number | string): number | null {
    const numeric = typeof id === 'number'
      ? id
      : /^\d+$/.test(id.trim())
        ? Number(id)
        : Number.NaN;
    return Number.isSafeInteger(numeric) && numeric > 0 ? numeric : null;
  }

  private toSummary(row: WriteupBaseRow): WriteupSummary {
    return {
      id: safeId(row.id),
      sourceKey: stringValue(row.sourceKey),
      challengeName: stringValue(row.challengeName),
      domain: stringValue(row.domain),
      difficulty: stringValue(row.difficulty),
      sourceRepo: stringValue(row.sourceRepo),
      sourceUrl: row.sourceUrl === null || row.sourceUrl === undefined ? null : stringValue(row.sourceUrl),
      status: stringValue(row.status),
      metadata: jsonSafe(row.metadata),
      createdAt: dateValue(row.createdAt),
      updatedAt: dateValue(row.updatedAt),
    };
  }

  private toRecord(row: WriteupRow): WriteupRecord {
    return {
      ...this.toSummary(row),
      markdown: stringValue(row.markdown),
    };
  }
}

interface WriteupBaseRow extends QueryResultRow {
  id: unknown;
  sourceKey: unknown;
  challengeName: unknown;
  domain: unknown;
  difficulty: unknown;
  sourceRepo: unknown;
  sourceUrl: unknown;
  status: unknown;
  metadata: unknown;
  createdAt: unknown;
  updatedAt: unknown;
}

interface WriteupSummaryRow extends WriteupBaseRow {
  totalCount: unknown;
}

interface WriteupRow extends WriteupBaseRow {
  markdown: unknown;
}

interface DomainRow extends QueryResultRow {
  domain: unknown;
  count: unknown;
}

import { Injectable } from '@nestjs/common';
import { QueryResultRow } from 'pg';
import { DatabaseService } from '../database/database.service';
import {
  PagedResult,
  WriteupSearchOptions,
} from './writeups.service';

type JsonPrimitive = string | number | boolean | null;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
const MAX_SOURCE_DOCUMENT_OFFSET = 100_000;

export interface SourceDocumentSummary {
  id: number | string;
  sourceKey: string;
  sourcePath: string;
  title: string;
  sourceRepo: string;
  metadata: JsonValue;
  createdAt: string;
  updatedAt: string;
}

export interface SourceDocumentRecord extends SourceDocumentSummary {
  markdown: string;
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
export class SourceDocumentsService {
  constructor(private readonly database: DatabaseService) {}

  async search(options: Pick<WriteupSearchOptions, 'query' | 'limit' | 'offset'> = {}): Promise<PagedResult<SourceDocumentSummary>> {
    const limit = options.limit === undefined || !Number.isFinite(options.limit)
      ? 20
      : Math.min(100, Math.max(0, Math.floor(options.limit)));
    const offset = options.offset === undefined || !Number.isFinite(options.offset)
      ? 0
      : Math.min(MAX_SOURCE_DOCUMENT_OFFSET, Math.max(0, Math.floor(options.offset)));
    const values: unknown[] = [];
    const query = options.query?.trim();
    const where = query
      ? (() => {
          values.push(query);
          return `WHERE search_vector @@ websearch_to_tsquery('simple', $${values.length})`;
        })()
      : '';
    values.push(limit, offset);
    const limitPosition = values.length - 1;
    const offsetPosition = values.length;
    const result = await this.database.query<SourceDocumentRow>(
      `SELECT id, source_key AS "sourceKey", source_path AS "sourcePath", title,
              source_repo AS "sourceRepo", metadata, created_at AS "createdAt",
              updated_at AS "updatedAt", COUNT(*) OVER() AS "totalCount"
         FROM source_documents
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

  async getById(id: number | string): Promise<SourceDocumentRecord | null> {
    const numeric = typeof id === 'number'
      ? id
      : /^\d+$/.test(id.trim())
        ? Number(id)
        : Number.NaN;
    if (!Number.isSafeInteger(numeric) || numeric <= 0) {
      return null;
    }
    const result = await this.database.query<SourceDocumentRowWithMarkdown>(
      `SELECT id, source_key AS "sourceKey", source_path AS "sourcePath", title,
              source_repo AS "sourceRepo", markdown, metadata,
              created_at AS "createdAt", updated_at AS "updatedAt"
         FROM source_documents
        WHERE id = $1
        LIMIT 1`,
      [numeric],
    );
    const row = result.rows[0];
    return row === undefined ? null : { ...this.toSummary(row), markdown: stringValue(row.markdown) };
  }

  private toSummary(row: SourceDocumentRow): SourceDocumentSummary {
    return {
      id: safeId(row.id),
      sourceKey: stringValue(row.sourceKey),
      sourcePath: stringValue(row.sourcePath),
      title: stringValue(row.title),
      sourceRepo: stringValue(row.sourceRepo),
      metadata: jsonSafe(row.metadata),
      createdAt: dateValue(row.createdAt),
      updatedAt: dateValue(row.updatedAt),
    };
  }
}

interface SourceDocumentRow extends QueryResultRow {
  id: unknown;
  sourceKey: unknown;
  sourcePath: unknown;
  title: unknown;
  sourceRepo: unknown;
  metadata: unknown;
  createdAt: unknown;
  updatedAt: unknown;
  totalCount: unknown;
}

interface SourceDocumentRowWithMarkdown extends SourceDocumentRow {
  markdown: unknown;
}

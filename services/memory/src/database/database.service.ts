import { Injectable, OnApplicationShutdown, OnModuleDestroy } from '@nestjs/common';
import { Pool, PoolClient, QueryResult, QueryResultRow } from 'pg';

export const DEFAULT_DATABASE_URL =
  'postgres://memory:memory-local-only@127.0.0.1:5434/memory';

/** Owns the process-wide PostgreSQL connection pool. */
@Injectable()
export class DatabaseService implements OnModuleDestroy, OnApplicationShutdown {
  private readonly pool: Pool;
  private closePromise: Promise<void> | null = null;

  constructor() {
    const connectionString = process.env.DATABASE_URL;
    this.pool = connectionString
      ? new Pool({ connectionString })
      : new Pool({
          host: process.env.PGHOST ?? '127.0.0.1',
          port: Number.parseInt(process.env.PGPORT ?? '5434', 10),
          database: process.env.PGDATABASE ?? 'memory',
          user: process.env.PGUSER ?? 'memory',
          password: process.env.PGPASSWORD ?? 'memory-local-only',
        });
  }

  query<T extends QueryResultRow = QueryResultRow>(
    text: string,
    values: unknown[] = [],
  ): Promise<QueryResult<T>> {
    return this.pool.query<T>(text, values);
  }

  /** Run a group of statements atomically on one checked-out client. */
  async withTransaction<T>(callback: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      const result = await callback(client);
      await client.query('COMMIT');
      return result;
    } catch (error) {
      try {
        await client.query('ROLLBACK');
      } catch {
        // Preserve the original error when rollback itself fails.
      }
      throw error;
    } finally {
      client.release();
    }
  }

  async close(): Promise<void> {
    if (this.closePromise === null) {
      this.closePromise = this.pool.end();
    }
    await this.closePromise;
  }

  async onModuleDestroy(): Promise<void> {
    await this.close();
  }

  async onApplicationShutdown(): Promise<void> {
    await this.close();
  }
}

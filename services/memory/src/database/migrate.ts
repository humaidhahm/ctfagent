import 'dotenv/config';
import { readdir, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { Pool } from 'pg';
import { DEFAULT_DATABASE_URL } from './database.service';

async function findMigrationsDirectory(): Promise<string> {
  const candidates = [resolve(process.cwd(), 'db', 'migrations'), resolve(__dirname, '..', '..', 'db', 'migrations')];
  for (const candidate of candidates) {
    try {
      const entries = await readdir(candidate);
      if (entries.some((entry) => entry.toLowerCase().endsWith('.sql'))) {
        return candidate;
      }
    } catch {
      // Try the next path; this also keeps the source and compiled layouts portable.
    }
  }
  throw new Error('Could not locate db/migrations');
}

export async function runMigrations(
  connectionString = process.env.DATABASE_URL,
): Promise<string[]> {
  const directory = await findMigrationsDirectory();
  const names = (await readdir(directory))
    .filter((name) => name.toLowerCase().endsWith('.sql'))
    .sort();
  const pool = connectionString
    ? new Pool({ connectionString })
    : new Pool({
        host: process.env.PGHOST ?? '127.0.0.1',
        port: Number.parseInt(process.env.PGPORT ?? '5434', 10),
        database: process.env.PGDATABASE ?? 'memory',
        user: process.env.PGUSER ?? 'memory',
        password: process.env.PGPASSWORD ?? 'memory-local-only',
      });
  const applied: string[] = [];

  try {
    for (const name of names) {
      const sql = await readFile(resolve(directory, name), 'utf8');
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await client.query(sql);
        await client.query('COMMIT');
        applied.push(name);
      } catch (error) {
        try {
          await client.query('ROLLBACK');
        } catch {
          // Preserve the migration error if rollback fails.
        }
        throw error;
      } finally {
        client.release();
      }
    }
  } finally {
    await pool.end();
  }
  return applied;
}

if (require.main === module) {
  void runMigrations()
    .then((applied) => {
      for (const migration of applied) {
        console.log(`Applied ${migration}`);
      }
    })
    .catch((error: unknown) => {
      console.error(error);
      process.exitCode = 1;
    });
}

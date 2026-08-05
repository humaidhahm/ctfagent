import 'dotenv/config';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { resolve, posix as posixPath } from 'node:path';
import { Readable } from 'node:stream';
import { parse } from 'csv-parse/sync';
import * as tar from 'tar';
import { DatabaseService } from '../database/database.service';

const DEFAULT_CSV_PATH = '../../../picoctf_writeups_real.csv';
const DEFAULT_ARCHIVE_PATH = '../../../github_trees/picoCTF__picoCTF.tar.gz';
const WRITEUP_SOURCE_REPO = 'Writeup Source';
const WRITEUP_SOURCE_URL = 'Writeup Source URL';
const WRITEUP_STATUS = 'Writeup Status';
const WRITEUP_MARKDOWN = 'Writeup Markdown';
const CHALLENGE_NAME = 'Challenge Name';
const DOMAIN = 'Domain';
const DIFFICULTY = 'Difficulty';

type CsvRow = Record<string, string>;

interface ArchiveDocument {
  memberPath: string;
  markdown: string;
  title: string;
  contentSha256: string;
  byteLength: number;
}

function requiredField(row: CsvRow, key: string, ordinal: number): string {
  const value = row[key];
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`CSV row ${ordinal} is missing ${key}`);
  }
  return value;
}

function titleFromMarkdown(memberPath: string, markdown: string): string {
  const heading = /^\s*#\s+(.+?)\s*$/m.exec(markdown)?.[1];
  if (heading !== undefined && heading.trim() !== '') {
    return heading.trim();
  }
  const base = posixPath.basename(memberPath).replace(/\.(?:markdown?|md)$/i, '');
  return base || memberPath;
}

async function readTarEntry(entry: Readable): Promise<Buffer> {
  const chunks: Buffer[] = [];
  for await (const chunk of entry) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk as Uint8Array));
  }
  return Buffer.concat(chunks);
}

export async function collectArchiveDocuments(archivePath: string): Promise<ArchiveDocument[]> {
  const pending: Array<Promise<ArchiveDocument>> = [];
  await tar.t({
    file: archivePath,
    onentry: (entry) => {
      const memberPath = String(entry.path ?? '').replaceAll('\\', '/');
      const lowerPath = memberPath.toLowerCase();
      const entryType = typeof entry.type === 'string' ? entry.type.toLowerCase() : '';
      const isRegularFile = entryType === '' || entryType === 'file';
      const isMarkdown = lowerPath.endsWith('.md') || lowerPath.endsWith('.markdown');
      if (!isMarkdown || !isRegularFile) {
        entry.resume();
        return;
      }
      pending.push(
        readTarEntry(entry as unknown as Readable).then((content) => {
          const markdown = content.toString('utf8');
          return {
            memberPath,
            markdown,
            title: titleFromMarkdown(memberPath, markdown),
            contentSha256: createHash('sha256').update(content).digest('hex'),
            byteLength: content.byteLength,
          };
        }),
      );
    },
  });
  return Promise.all(pending);
}

async function upsertWriteups(
  database: DatabaseService,
  rows: CsvRow[],
  inputPath: string,
): Promise<number> {
  await database.withTransaction(async (client) => {
    for (const [index, row] of rows.entries()) {
      const ordinal = index + 1;
      const challengeName = requiredField(row, CHALLENGE_NAME, ordinal);
      const domain = requiredField(row, DOMAIN, ordinal);
      const difficulty = requiredField(row, DIFFICULTY, ordinal);
      const sourceRepo = requiredField(row, WRITEUP_SOURCE_REPO, ordinal);
      const status = requiredField(row, WRITEUP_STATUS, ordinal);
      const markdown = row[WRITEUP_MARKDOWN];
      if (typeof markdown !== 'string') {
        throw new Error(`CSV row ${ordinal} is missing ${WRITEUP_MARKDOWN}`);
      }
      const sourceUrlValue = row[WRITEUP_SOURCE_URL]?.trim() ?? '';
      const metadata = {
        rowOrdinal: ordinal,
        inputPath,
        contentSha256: createHash('sha256').update(markdown, 'utf8').digest('hex'),
      };
      await client.query(
        `INSERT INTO writeups
           (source_key, challenge_name, domain, difficulty, source_repo, source_url,
            status, markdown, metadata, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, now())
         ON CONFLICT (source_key) DO UPDATE SET
           challenge_name = EXCLUDED.challenge_name,
           domain = EXCLUDED.domain,
           difficulty = EXCLUDED.difficulty,
           source_repo = EXCLUDED.source_repo,
           source_url = EXCLUDED.source_url,
           status = EXCLUDED.status,
           markdown = EXCLUDED.markdown,
           metadata = EXCLUDED.metadata,
           updated_at = now()`,
        [
          `csv:${ordinal}:${challengeName}`,
          challengeName,
          domain,
          difficulty,
          sourceRepo,
          sourceUrlValue === '' ? null : sourceUrlValue,
          status,
          markdown,
          JSON.stringify(metadata),
        ],
      );
    }
  });
  return rows.length;
}

async function upsertSourceDocuments(
  database: DatabaseService,
  documents: ArchiveDocument[],
  archivePath: string,
): Promise<number> {
  await database.withTransaction(async (client) => {
    for (const document of documents) {
      const metadata = {
        archivePath,
        memberPath: document.memberPath,
        contentSha256: document.contentSha256,
        byteLength: document.byteLength,
      };
      await client.query(
        `INSERT INTO source_documents
           (source_key, source_path, title, source_repo, markdown, metadata, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6::jsonb, now())
         ON CONFLICT (source_key) DO UPDATE SET
           source_path = EXCLUDED.source_path,
           title = EXCLUDED.title,
           source_repo = EXCLUDED.source_repo,
           markdown = EXCLUDED.markdown,
           metadata = EXCLUDED.metadata,
           updated_at = now()`,
        [
          `archive:${document.memberPath}`,
          document.memberPath,
          document.title,
          'picoCTF/picoCTF',
          document.markdown,
          JSON.stringify(metadata),
        ],
      );
    }
  });
  return documents.length;
}

export async function importData(
  csvPath = resolve(process.cwd(), process.env.CSV_PATH ?? DEFAULT_CSV_PATH),
  archivePath = resolve(process.cwd(), process.env.PICOCTF_ARCHIVE_PATH ?? DEFAULT_ARCHIVE_PATH),
): Promise<{ writeups: number; sourceDocuments: number }> {
  const csvText = await readFile(csvPath, 'utf8');
  const rows = parse(csvText, {
    bom: true,
    columns: true,
    skip_empty_lines: true,
    relax_column_count: false,
  }) as CsvRow[];
  const documents = await collectArchiveDocuments(archivePath);
  const database = new DatabaseService();
  try {
    const writeupCount = await upsertWriteups(database, rows, csvPath);
    const sourceDocumentCount = await upsertSourceDocuments(database, documents, archivePath);
    return { writeups: writeupCount, sourceDocuments: sourceDocumentCount };
  } finally {
    await database.close();
  }
}

if (require.main === module) {
  void importData()
    .then((counts) => {
      console.log(`Imported ${counts.writeups} writeups and ${counts.sourceDocuments} source documents.`);
    })
    .catch((error: unknown) => {
      console.error(error);
      process.exitCode = 1;
    });
}

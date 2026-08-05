CREATE TABLE IF NOT EXISTS writeups (
  id BIGSERIAL PRIMARY KEY,
  source_key TEXT NOT NULL UNIQUE,
  challenge_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  source_repo TEXT NOT NULL,
  source_url TEXT,
  status TEXT NOT NULL,
  markdown TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  search_vector TSVECTOR GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(challenge_name, '') || ' ' || coalesce(domain, '') || ' ' || coalesce(markdown, ''))
  ) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS writeups_search_vector_idx ON writeups USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS writeups_domain_idx ON writeups (domain);
CREATE INDEX IF NOT EXISTS writeups_difficulty_idx ON writeups (difficulty);
CREATE INDEX IF NOT EXISTS writeups_challenge_name_idx ON writeups (lower(challenge_name));

CREATE TABLE IF NOT EXISTS source_documents (
  id BIGSERIAL PRIMARY KEY,
  source_key TEXT NOT NULL UNIQUE,
  source_path TEXT NOT NULL,
  title TEXT NOT NULL,
  source_repo TEXT NOT NULL,
  markdown TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  search_vector TSVECTOR GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(source_path, '') || ' ' || coalesce(markdown, ''))
  ) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS source_documents_search_vector_idx ON source_documents USING GIN (search_vector);

CREATE TABLE IF NOT EXISTS web_references (
  url TEXT PRIMARY KEY,
  status_code INTEGER NOT NULL,
  content_type TEXT,
  title TEXT,
  body TEXT NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

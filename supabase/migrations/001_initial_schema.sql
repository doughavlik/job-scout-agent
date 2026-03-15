-- Job Scout: Initial database schema
-- Run this in your Supabase SQL Editor to set up all tables.

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    notification_threshold INTEGER NOT NULL DEFAULT 70,
    resume_ref  TEXT,          -- optional: path or URL to resume
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- SEARCHES
-- ============================================================
CREATE TABLE IF NOT EXISTS searches (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                    TEXT NOT NULL,
    keywords                TEXT NOT NULL,
    location                TEXT,
    remote                  TEXT CHECK (remote IN ('onsite', 'hybrid', 'remote')),
    radius_km               INTEGER,
    excluded_companies      JSONB NOT NULL DEFAULT '[]',
    excluded_title_keywords JSONB NOT NULL DEFAULT '[]',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

-- ============================================================
-- JOBS
-- ============================================================
CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id       UUID NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    url             TEXT NOT NULL,
    source          TEXT NOT NULL,
    description     TEXT,
    salary_min      NUMERIC,
    salary_max      NUMERIC,
    salary_currency TEXT,
    remote          TEXT,
    date_posted     TEXT,
    external_id     TEXT,
    dedup_hash      TEXT UNIQUE NOT NULL,
    seen_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_dedup_hash ON jobs(dedup_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_search_id  ON jobs(search_id);

-- ============================================================
-- SCORES
-- ============================================================
CREATE TABLE IF NOT EXISTS scores (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    score       INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    rationale   TEXT,
    model_used  TEXT NOT NULL,
    scored_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scores_job_id ON scores(job_id);
CREATE INDEX IF NOT EXISTS idx_scores_score  ON scores(score DESC);

-- ============================================================
-- Row Level Security (optional but recommended)
-- ============================================================
-- Enable RLS on all tables. The service-role key used by
-- GitHub Actions bypasses RLS, so no policies are needed for
-- the MVP. If you later add a web dashboard with user auth,
-- add policies here.

ALTER TABLE users    ENABLE ROW LEVEL SECURITY;
ALTER TABLE searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE scores   ENABLE ROW LEVEL SECURITY;

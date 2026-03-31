# Job Scout Agent

Autonomous job search agent that monitors job boards for Customer Success roles, scores them with AI, and emails you the best matches. Runs on a schedule via GitHub Actions.

## How It Works

1. **Fetch** — Queries Adzuna for jobs matching your saved searches
2. **Deduplicate** — Skips jobs already seen (stored in Supabase)
3. **Pre-filter** — Drops jobs that fail hard rules (excluded companies, title keywords)
4. **AI Score** — Sends surviving jobs + your resume/preferences to Gemini Flash, gets a 1–100 relevance score
5. **Notify** — Emails you a digest of jobs scoring at or above your threshold

Runs every 2 hours via GitHub Actions cron. You can also trigger it manually.

## Setup

### 1. Fork / Clone This Repo

```bash
git clone https://github.com/your-user/job-scout-agent.git
cd job-scout-agent
```

### 2. Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a free project
2. Open the **SQL Editor** in your Supabase dashboard
3. Paste the contents of `supabase/migrations/001_initial_schema.sql` and run it
4. Copy your project URL and **service_role** key from Settings → API

### 3. Get API Keys

| Service | Where to get it |
|---------|----------------|
| **Adzuna** | [developer.adzuna.com](https://developer.adzuna.com) — sign up for free (250 req/day) |
| **Gemini** | [aistudio.google.com](https://aistudio.google.com) — create an API key |
| **Gmail** | Enable 2FA on your Google account, then create an [App Password](https://myaccount.google.com/apppasswords) |

### 4. Configure Your Searches

Edit `config.yaml` to set your email, notification threshold, and search criteria.

### 5. Fill In Your Resume & Preferences

Edit `master_resume.md` and `preferences.md` with your actual background and job preferences. The AI scorer reads both to judge how well each job matches you.

### 6. Add GitHub Secrets

In your repo, go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your Supabase **service_role** key |
| `ADZUNA_APP_ID` | Adzuna application ID |
| `ADZUNA_APP_KEY` | Adzuna API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GMAIL_ADDRESS` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail app-specific password |

### 7. Test It

Trigger the workflow manually from the **Actions** tab, or run locally:

```bash
pip install -r requirements.txt

export SUPABASE_URL=...
export SUPABASE_KEY=...
export ADZUNA_APP_ID=...
export ADZUNA_APP_KEY=...
export GEMINI_API_KEY=...
export GMAIL_ADDRESS=...
export GMAIL_APP_PASSWORD=...

cd src && python -m job_scout.main
```

## Operating Modes

Job Scout supports two distinct modes, selected via the `--mode` CLI flag or the `MODE` environment variable.

### Full Mode (default)

Runs the complete job-search pipeline: fetch → deduplicate → pre-filter → AI score → email notification. This is what runs every 2 hours via `job-scout.yml`.

```bash
# Both are equivalent:
python -m job_scout.main
python -m job_scout.main --mode full
```

Requires all secrets: `SUPABASE_URL`, `SUPABASE_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `GEMINI_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`.

### Keepalive Mode

A lightweight mode whose sole purpose is to prevent the free Supabase project from being paused due to inactivity. Supabase pauses free-tier projects after 7 days of no database activity.

This mode performs a single read query against the database and exits immediately. **No LLM/AI APIs are called**, so it has effectively zero AI cost.

Runs every 3 days via `keepalive.yml`.

```bash
python -m job_scout.main --mode keepalive
# or:
MODE=keepalive python -m job_scout.main
```

Only requires `SUPABASE_URL` and `SUPABASE_KEY`.

## Project Structure

```
├── config.yaml                  # Search criteria & user settings
├── master_resume.md             # Your resume (used by AI scorer)
├── preferences.md               # Your job preferences (used by AI scorer)
├── requirements.txt
├── src/job_scout/
│   ├── main.py                  # Orchestrator — mode selection + full pipeline
│   ├── keepalive.py             # Keepalive mode — lightweight Supabase ping
│   ├── models.py                # Data classes (Job, ScoredJob, SearchConfig)
│   ├── database.py              # Supabase client
│   ├── filters.py               # Rule-based pre-filters
│   ├── scoring.py               # Gemini AI scoring
│   ├── notifier.py              # Gmail SMTP email sender
│   └── sources/
│       ├── base.py              # JobSource abstract base class
│       └── adzuna.py            # Adzuna API plugin
├── supabase/migrations/
│   └── 001_initial_schema.sql   # Database schema
└── .github/workflows/
    ├── job-scout.yml            # Full mode — runs every 2 hours
    └── keepalive.yml            # Keepalive mode — runs every 3 days
```

## Adding a New Job Source

1. Create a new file in `src/job_scout/sources/` (e.g., `jsearch.py`)
2. Implement the `JobSource` abstract base class from `sources/base.py`
3. Instantiate it in `main.py` alongside `AdzunaSource`

## Multi-User / Forking

The database schema supports multiple users via `user_id` foreign keys. To deploy your own instance:

1. Fork this repo
2. Create your own Supabase project and run the migration
3. Add your own secrets
4. Customize `config.yaml`, `master_resume.md`, and `preferences.md`

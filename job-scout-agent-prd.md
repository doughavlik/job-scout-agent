# PRD: Job Scout — Autonomous Job Search Agent

## Overview

Job Scout is a Python-based autonomous agent that monitors job boards for Customer Success roles, scores them using AI, and emails high-scoring matches to the user. It runs as a scheduled GitHub Actions workflow on a public repository, with Supabase (PostgreSQL) for persistent storage.

## Problem

Manually checking job boards multiple times daily is tedious and leads to missed opportunities. An automated agent should surface only high-relevance roles, saving time and ensuring no strong match is overlooked.

## Architecture

**Runtime:** GitHub Actions cron workflow, executing every 2 hours (`0 */2 * * *`).
**Language:** Python 3.11+
**Database:** Supabase (PostgreSQL) — stores seen jobs, scores, user config, and search criteria.
**LLM:** Google Gemini Flash via API — scores job-to-candidate fit.
**Email:** Gmail SMTP with App Password — sends notifications when jobs exceed the user's score threshold. (Simpler than OAuth2 for a GitHub Actions bot; requires 2FA enabled on the Google account and an app-specific password.)
**Job Sources:** Adzuna API (free tier: 250 req/day). Design a `JobSource` abstract base class so additional sources (JSearch, The Muse, etc.) can be added as plugins.

## Core Workflow

1. **Fetch listings:** Query Adzuna for each saved search configuration (keywords, location, remote [onsite, hybrid, remote], radius, company size filters). Deduplicate against jobs already in the database.
2. **Pre-filter (rules):** Discard jobs that fail hard filters — excluded companies, irrelevant titles, missing location. This is fast and free.
3. **AI scoring:** Send surviving jobs plus the user's resume and preferences document to Gemini Flash. Prompt the LLM to return a 1–100 relevance score and a 2–3 sentence rationale for each job.
4. **Store results:** Write all evaluated jobs (including low scorers) to Supabase with their score, rationale, source, and timestamp.
5. **Notify:** For jobs scoring at or above the user's configurable threshold (default: 70/100), send an email containing: job title, company, remote, location, salary (if available), score, rationale, and a direct apply link.

## Data Model

- **`searches`** — saved search configs (keywords, remote, location, radius, filters, user_id).
- **`jobs`** — listing data, source, date seen, dedup hash.
- **`scores`** — job_id, score, rationale, model used, timestamp.
- **`users`** — email, notification threshold, resume reference, preferences.

## Configuration

All secrets (API keys, Supabase URL, Gmail App Password) are stored as GitHub Actions encrypted secrets. User-facing config (search criteria, threshold, preferences doc) lives in a `config.yaml` checked into the repo, with sensitive fields referencing environment variables.

## Multi-User Considerations

The database schema includes a `user_id` foreign key on searches, scores, and notification preferences. The MVP serves a single user, but the schema supports multiple users without migration. The README should document how a second user can fork the repo and deploy their own instance.

## Success Metrics

- Agent runs reliably on schedule with no manual intervention.
- Zero duplicate notifications for the same job listing.
- AI scoring aligns with user's subjective relevance at least 80% of the time (measured by user feedback over first 2 weeks).

## Out of Scope (MVP)

Auto-applying to jobs, browser-based scraping, a web dashboard, and multi-user authentication.

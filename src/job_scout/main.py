"""
Main orchestrator for Job Scout.

Operating modes
---------------
full (default)
    The complete job-search pipeline: fetch → deduplicate → pre-filter →
    AI score → email notification. Requires all secrets (Supabase, Adzuna,
    Gemini, Gmail). Runs every 2 hours via GitHub Actions (job-scout.yml).

keepalive
    Lightweight mode whose sole purpose is to prevent the free Supabase
    project from being paused due to inactivity. Performs a single read
    query against the database and exits. No LLM/AI APIs are called.
    Runs every 3 days via GitHub Actions (keepalive.yml).

Selecting a mode
----------------
Pass ``--mode keepalive`` on the command line, or set the ``MODE``
environment variable to ``keepalive``.  Anything else (or omitting the
flag entirely) runs full mode.

Examples::

    # Full mode (default)
    python -m job_scout.main
    python -m job_scout.main --mode full

    # Keepalive mode
    python -m job_scout.main --mode keepalive
    MODE=keepalive python -m job_scout.main
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

from .database import Database
from .filters import apply_filters
from .keepalive import run_keepalive
from .models import SearchConfig, ScoredJob
from .notifier import send_notification
from .scoring import Scorer
from .sources.adzuna import AdzunaSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(path: str | None = None) -> dict:
    if path is None:
        # Look for config.yaml in the repo root (parent of src/)
        candidates = [
            Path("config.yaml"),
            Path(__file__).resolve().parent.parent.parent / "config.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                path = str(candidate)
                break
        else:
            raise FileNotFoundError("config.yaml not found")
    with open(path) as f:
        return yaml.safe_load(f)


def load_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _resolve_path(path_str: str, config_dir: Path) -> Path:
    """Resolve a path relative to the config file's directory."""
    p = Path(path_str)
    if p.is_absolute():
        return p
    resolved = config_dir / p
    if resolved.exists():
        return resolved
    # Fallback to cwd
    return p


def run() -> None:
    logger.info("=== Job Scout starting ===")

    config = load_config()
    user_cfg = config["user"]

    # Resolve email: support ${GMAIL_ADDRESS} env var syntax
    email = user_cfg["email"]
    if email.startswith("${") and email.endswith("}"):
        env_var = email[2:-1]
        email = os.environ.get(env_var, email)
    user_cfg["email"] = email

    # Resolve file paths relative to config.yaml location
    config_dir = Path("config.yaml").resolve().parent
    for candidate in [Path(__file__).resolve().parent.parent.parent / "config.yaml"]:
        if candidate.exists():
            config_dir = candidate.parent
            break

    resume = load_text_file(str(_resolve_path(user_cfg["resume_path"], config_dir)))
    preferences = load_text_file(str(_resolve_path(user_cfg["preferences_path"], config_dir)))

    db = Database()
    user_id = db.get_or_create_user(
        email=user_cfg["email"],
        threshold=user_cfg["notification_threshold"],
    )

    adzuna_cfg = config.get("adzuna", {})
    source = AdzunaSource(
        country=adzuna_cfg.get("country", "us"),
        results_per_page=adzuna_cfg.get("results_per_page", 50),
        max_days_old=adzuna_cfg.get("max_days_old", 1),
    )

    scorer = Scorer(resume=resume, preferences=preferences)
    threshold = user_cfg["notification_threshold"]
    all_notifiable: list[ScoredJob] = []

    for search_cfg in config["searches"]:
        search = SearchConfig(
            name=search_cfg["name"],
            keywords=search_cfg["keywords"],
            location=search_cfg["location"],
            remote=search_cfg["remote"],
            radius_km=search_cfg.get("radius_km"),
            excluded_companies=search_cfg.get("excluded_companies", []),
            excluded_title_keywords=search_cfg.get("excluded_title_keywords", []),
        )
        search_id = db.upsert_search(user_id, search_cfg)

        # Step 1: Fetch listings
        logger.info("Fetching jobs for search: %s", search.name)
        raw_jobs = source.fetch(search)
        if not raw_jobs:
            logger.info("No jobs returned for '%s'", search.name)
            continue

        # Step 2: Deduplicate against DB
        new_jobs = db.filter_unseen_jobs(raw_jobs)
        logger.info("%d new jobs (of %d fetched) for '%s'", len(new_jobs), len(raw_jobs), search.name)
        if not new_jobs:
            continue

        # Step 3: Pre-filter (rules)
        filtered_jobs = apply_filters(new_jobs, search)
        if not filtered_jobs:
            logger.info("All new jobs filtered out for '%s'", search.name)
            continue

        # Step 4: AI scoring
        for job in filtered_jobs:
            scored = scorer.score(job)
            job_id = db.insert_job(job, search_id)
            db.insert_score(job_id, scored)
            logger.info(
                "  %s at %s — score %d", job.title, job.company, scored.score
            )
            if scored.score >= threshold:
                all_notifiable.append(scored)

    # Step 5: Notify
    if all_notifiable:
        all_notifiable.sort(key=lambda s: s.score, reverse=True)
        logger.info("Sending notification for %d jobs above threshold %d", len(all_notifiable), threshold)
        send_notification(user_cfg["email"], all_notifiable)
    else:
        logger.info("No jobs above threshold %d this run.", threshold)

    logger.info("=== Job Scout finished ===")


def _parse_mode() -> str:
    """
    Determine the operating mode from CLI args or environment variable.

    Priority: --mode flag > MODE env var > default ("full").
    Valid values: "full", "keepalive".
    """
    parser = argparse.ArgumentParser(
        description="Job Scout — autonomous job search agent",
        add_help=True,
    )
    parser.add_argument(
        "--mode",
        choices=["full", "keepalive"],
        default=None,
        help=(
            "Operating mode. 'full' runs the complete job-search pipeline "
            "(default). 'keepalive' performs a lightweight Supabase ping to "
            "prevent the free project from being paused due to inactivity."
        ),
    )
    args, _ = parser.parse_known_args()

    if args.mode:
        return args.mode

    # Fall back to MODE environment variable
    env_mode = os.environ.get("MODE", "full").lower()
    if env_mode not in ("full", "keepalive"):
        logger.warning("Unknown MODE=%r — defaulting to 'full'", env_mode)
        return "full"
    return env_mode


if __name__ == "__main__":
    mode = _parse_mode()
    if mode == "keepalive":
        run_keepalive()
    else:
        run()

"""Main orchestrator for Job Scout."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import yaml

from .database import Database
from .filters import apply_filters
from .models import SearchConfig, ScoredJob
from .notifier import send_notification
from .scoring import Scorer
from .sources.adzuna import AdzunaSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def run() -> None:
    logger.info("=== Job Scout starting ===")

    config = load_config()
    user_cfg = config["user"]
    resume = load_text_file(user_cfg["resume_path"])
    preferences = load_text_file(user_cfg["preferences_path"])

    db = Database()
    user_id = db.get_or_create_user(
        email=user_cfg["email"],
        threshold=user_cfg["notification_threshold"],
    )

    adzuna_cfg = config.get("adzuna", {})
    source = AdzunaSource(
        country=adzuna_cfg.get("country", "us"),
        results_per_page=adzuna_cfg.get("results_per_page", 50),
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


if __name__ == "__main__":
    run()

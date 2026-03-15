"""Supabase database layer for Job Scout."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from supabase import Client, create_client

from .models import Job, ScoredJob

logger = logging.getLogger(__name__)


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


class Database:
    def __init__(self, client: Client | None = None):
        self.client = client or get_client()

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_or_create_user(self, email: str, threshold: int = 70) -> str:
        """Return user id, creating the row if it doesn't exist."""
        resp = self.client.table("users").select("id").eq("email", email).execute()
        if resp.data:
            return resp.data[0]["id"]
        resp = (
            self.client.table("users")
            .insert({"email": email, "notification_threshold": threshold})
            .execute()
        )
        return resp.data[0]["id"]

    # ------------------------------------------------------------------
    # Searches
    # ------------------------------------------------------------------

    def upsert_search(self, user_id: str, config: dict) -> str:
        """Upsert a search config row and return its id."""
        resp = (
            self.client.table("searches")
            .select("id")
            .eq("user_id", user_id)
            .eq("name", config["name"])
            .execute()
        )
        if resp.data:
            return resp.data[0]["id"]
        row = {
            "user_id": user_id,
            "name": config["name"],
            "keywords": config["keywords"],
            "location": config["location"],
            "remote": config["remote"],
            "radius_km": config.get("radius_km"),
            "excluded_companies": config.get("excluded_companies", []),
            "excluded_title_keywords": config.get("excluded_title_keywords", []),
        }
        resp = self.client.table("searches").insert(row).execute()
        return resp.data[0]["id"]

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def job_seen(self, dedup_hash: str) -> bool:
        resp = (
            self.client.table("jobs")
            .select("id")
            .eq("dedup_hash", dedup_hash)
            .execute()
        )
        return bool(resp.data)

    def filter_unseen_jobs(self, jobs: list[Job]) -> list[Job]:
        """Return only jobs not already in the database."""
        if not jobs:
            return []
        hashes = [j.dedup_hash for j in jobs]
        resp = (
            self.client.table("jobs")
            .select("dedup_hash")
            .in_("dedup_hash", hashes)
            .execute()
        )
        seen = {row["dedup_hash"] for row in resp.data}
        return [j for j in jobs if j.dedup_hash not in seen]

    def insert_job(self, job: Job, search_id: str) -> str:
        row = {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "source": job.source,
            "description": job.description,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "remote": job.remote,
            "date_posted": job.date_posted,
            "external_id": job.external_id,
            "dedup_hash": job.dedup_hash,
            "search_id": search_id,
            "seen_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = self.client.table("jobs").insert(row).execute()
        return resp.data[0]["id"]

    # ------------------------------------------------------------------
    # Scores
    # ------------------------------------------------------------------

    def insert_score(self, job_id: str, scored: ScoredJob) -> None:
        row = {
            "job_id": job_id,
            "score": scored.score,
            "rationale": scored.rationale,
            "model_used": scored.model_used,
            "scored_at": scored.scored_at.isoformat(),
        }
        self.client.table("scores").insert(row).execute()

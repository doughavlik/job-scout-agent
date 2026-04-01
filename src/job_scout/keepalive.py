"""
Keepalive mode for Job Scout.

Purpose: Prevent the free Supabase project from being paused due to inactivity.
Supabase pauses free-tier projects after 7 days of no database activity.
This module performs a lightweight read query every 3 days to keep the project active.

No LLM/AI APIs are called in this mode — only a single Supabase read.
"""

from __future__ import annotations

import logging

from .database import get_client

logger = logging.getLogger(__name__)


def run_keepalive() -> None:
    """
    Perform a minimal Supabase read to register database activity.

    This query fetches the most recently seen job row (limit 1), which is
    enough for Supabase to count the project as active. No AI APIs are called,
    no jobs are fetched or scored, and no emails are sent.
    """
    logger.info("=== Job Scout keepalive starting ===")

    client = get_client()

    # Simple read: fetch the single most-recently-seen job.
    # This registers real database activity on Supabase without touching
    # any AI APIs or external job-board APIs.
    resp = (
        client.table("jobs")
        .select("id, title, seen_at")
        .order("seen_at", desc=True)
        .limit(1)
        .execute()
    )

    if resp.data:
        row = resp.data[0]
        logger.info(
            "Keepalive ping successful. Most recent job in DB: '%s' (id=%s, seen_at=%s)",
            row.get("title", "unknown"),
            row.get("id", "?"),
            row.get("seen_at", "?"),
        )
    else:
        # No jobs in the DB yet — do a lightweight read on the users table instead
        # to still register activity.
        resp2 = client.table("users").select("id").limit(1).execute()
        logger.info(
            "Keepalive ping successful (jobs table is empty; pinged users table). "
            "Rows returned: %d",
            len(resp2.data),
        )

    logger.info("=== Job Scout keepalive finished ===")

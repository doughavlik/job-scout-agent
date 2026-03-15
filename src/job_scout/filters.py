"""Rule-based pre-filters (fast, free — runs before AI scoring)."""

from __future__ import annotations

import logging

from .models import Job, SearchConfig

logger = logging.getLogger(__name__)


def apply_filters(jobs: list[Job], search: SearchConfig) -> list[Job]:
    """Discard jobs that fail hard rules. Returns survivors."""
    passed: list[Job] = []
    for job in jobs:
        if _is_excluded_company(job, search):
            logger.debug("Filtered out (company): %s at %s", job.title, job.company)
            continue
        if _has_excluded_title_keyword(job, search):
            logger.debug("Filtered out (title keyword): %s", job.title)
            continue
        if not job.title.strip():
            logger.debug("Filtered out (empty title)")
            continue
        passed.append(job)

    filtered_count = len(jobs) - len(passed)
    if filtered_count:
        logger.info("Pre-filter removed %d / %d jobs", filtered_count, len(jobs))
    return passed


def _is_excluded_company(job: Job, search: SearchConfig) -> bool:
    company_lower = job.company.lower()
    return any(exc.lower() in company_lower for exc in search.excluded_companies)


def _has_excluded_title_keyword(job: Job, search: SearchConfig) -> bool:
    title_lower = job.title.lower()
    return any(kw.lower() in title_lower for kw in search.excluded_title_keywords)

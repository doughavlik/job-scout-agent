"""Adzuna job source plugin."""

from __future__ import annotations

import logging
import os

import httpx

from ..models import Job, SearchConfig
from .base import JobSource

logger = logging.getLogger(__name__)

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"


class AdzunaSource(JobSource):
    def __init__(self, country: str = "us", results_per_page: int = 50):
        self.app_id = os.environ["ADZUNA_APP_ID"]
        self.app_key = os.environ["ADZUNA_APP_KEY"]
        self.country = country
        self.results_per_page = results_per_page

    @property
    def name(self) -> str:
        return "Adzuna"

    def fetch(self, search: SearchConfig) -> list[Job]:
        params: dict = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": self.results_per_page,
            "what": search.keywords,
            "content-type": "application/json",
        }
        if search.location:
            params["where"] = search.location
        if search.radius_km is not None:
            params["distance"] = search.radius_km

        url = f"{ADZUNA_BASE}/{self.country}/search/1"
        logger.info("Adzuna query: %s params=%s", url, {k: v for k, v in params.items() if k not in ("app_id", "app_key")})

        try:
            resp = httpx.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Adzuna API error: %s", exc)
            return []

        data = resp.json()
        results = data.get("results", [])
        logger.info("Adzuna returned %d results for '%s'", len(results), search.name)

        jobs: list[Job] = []
        for r in results:
            salary_min = r.get("salary_min")
            salary_max = r.get("salary_max")
            jobs.append(
                Job(
                    title=r.get("title", ""),
                    company=r.get("company", {}).get("display_name", "Unknown"),
                    location=r.get("location", {}).get("display_name", ""),
                    url=r.get("redirect_url", ""),
                    source=self.name,
                    description=r.get("description", ""),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency="USD" if (salary_min or salary_max) else None,
                    remote=search.remote,
                    date_posted=r.get("created"),
                    external_id=str(r.get("id", "")),
                )
            )
        return jobs

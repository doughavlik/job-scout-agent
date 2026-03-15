"""Data models for Job Scout."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchConfig:
    name: str
    keywords: str
    location: str
    remote: str  # "onsite" | "hybrid" | "remote"
    radius_km: int | None = None
    excluded_companies: list[str] = field(default_factory=list)
    excluded_title_keywords: list[str] = field(default_factory=list)


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    source: str
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    remote: str | None = None  # "onsite" | "hybrid" | "remote"
    date_posted: str | None = None
    external_id: str | None = None

    @property
    def dedup_hash(self) -> str:
        raw = f"{self.title}|{self.company}|{self.url}".lower().strip()
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class ScoredJob:
    job: Job
    score: int  # 1-100
    rationale: str
    model_used: str
    scored_at: datetime = field(default_factory=datetime.utcnow)

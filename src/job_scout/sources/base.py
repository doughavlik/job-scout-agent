"""Abstract base class for job sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Job, SearchConfig


class JobSource(ABC):
    """Plugin interface for job board APIs."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable source name, e.g. 'Adzuna'."""

    @abstractmethod
    def fetch(self, search: SearchConfig) -> list[Job]:
        """Fetch jobs matching the search config. Returns a list of Job objects."""

"""AI scoring via Google Gemini Flash."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

from google import genai

from .models import Job, ScoredJob

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.0-flash"

SCORE_PROMPT = """\
You are an expert job-match evaluator.

## Candidate Resume
{resume}

## Candidate Preferences
{preferences}

## Job Listing
- **Title:** {title}
- **Company:** {company}
- **Location:** {location}
- **Remote:** {remote}
- **Salary:** {salary}
- **Description:** {description}

## Instructions
Rate how well this job matches the candidate on a scale of 1–100.
Return ONLY a JSON object with exactly two keys:
- "score": an integer 1–100
- "rationale": a 2–3 sentence explanation

Example:
{{"score": 82, "rationale": "Strong match because..."}}
"""


def _format_salary(job: Job) -> str:
    if job.salary_min and job.salary_max:
        return f"{job.salary_currency} {job.salary_min:,.0f}–{job.salary_max:,.0f}"
    if job.salary_min:
        return f"{job.salary_currency} {job.salary_min:,.0f}+"
    if job.salary_max:
        return f"Up to {job.salary_currency} {job.salary_max:,.0f}"
    return "Not listed"


class Scorer:
    def __init__(self, resume: str, preferences: str):
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.resume = resume
        self.preferences = preferences

    def score(self, job: Job) -> ScoredJob:
        prompt = SCORE_PROMPT.format(
            resume=self.resume,
            preferences=self.preferences,
            title=job.title,
            company=job.company,
            location=job.location,
            remote=job.remote or "Unknown",
            salary=_format_salary(job),
            description=job.description[:3000],
        )

        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )
            text = response.text.strip()
            # Strip markdown code fences if present
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            result = json.loads(text)
            score = max(1, min(100, int(result["score"])))
            rationale = str(result["rationale"])
        except Exception as exc:
            logger.error("Scoring failed for '%s': %s", job.title, exc)
            score = 0
            rationale = f"Scoring error: {exc}"

        return ScoredJob(
            job=job,
            score=score,
            rationale=rationale,
            model_used=MODEL_NAME,
            scored_at=datetime.now(timezone.utc),
        )

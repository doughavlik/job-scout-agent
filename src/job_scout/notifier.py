"""Email notifications via Gmail SMTP with App Password."""

from __future__ import annotations

import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .models import ScoredJob

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Location buckets: display name → list of patterns to match in job location
LOCATION_BUCKETS = [
    ("Nashville (On-site / Hybrid)", ["nashville"]),
    ("Austin (On-site / Hybrid)", ["austin"]),
    ("Houston (On-site / Hybrid)", ["houston"]),
]


def _format_salary(job) -> str:
    if job.salary_min and job.salary_max:
        return f"{job.salary_currency} {job.salary_min:,.0f} – {job.salary_max:,.0f}"
    if job.salary_min:
        return f"{job.salary_currency} {job.salary_min:,.0f}+"
    if job.salary_max:
        return f"Up to {job.salary_currency} {job.salary_max:,.0f}"
    return "Not listed"


def _format_date(date_str: str | None) -> str:
    if not date_str:
        return "N/A"
    # Adzuna dates look like "2026-03-15T10:00:00Z" — show just the date
    match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    return match.group(1) if match else date_str[:10]


def _is_location_match(job_location: str, patterns: list[str]) -> bool:
    loc_lower = job_location.lower()
    return any(p in loc_lower for p in patterns)


def _is_onsite_or_hybrid(scored: ScoredJob) -> bool:
    remote = (scored.job.remote or "").lower()
    return remote in ("onsite", "hybrid", "on-site")


def _categorize_jobs(scored_jobs: list[ScoredJob]) -> list[tuple[str, list[ScoredJob]]]:
    """
    Split jobs into sections:
      1. Top 3 on-site/hybrid per location (Nashville, Austin, Houston)
      2. Top 3 all other jobs
      3. Remaining on-site/hybrid per location
      4. Remaining all other jobs
    """
    # Sort all by score descending
    scored_jobs = sorted(scored_jobs, key=lambda s: s.score, reverse=True)

    # Bucket jobs by location (on-site/hybrid only) vs "other"
    location_jobs: dict[str, list[ScoredJob]] = {name: [] for name, _ in LOCATION_BUCKETS}
    other_jobs: list[ScoredJob] = []

    for sj in scored_jobs:
        placed = False
        if _is_onsite_or_hybrid(sj):
            for name, patterns in LOCATION_BUCKETS:
                if _is_location_match(sj.job.location, patterns):
                    location_jobs[name].append(sj)
                    placed = True
                    break
        if not placed:
            other_jobs.append(sj)

    sections: list[tuple[str, list[ScoredJob]]] = []

    # Top 3 per location
    top_remaining: dict[str, list[ScoredJob]] = {}
    for name, _ in LOCATION_BUCKETS:
        jobs = location_jobs[name]
        top = jobs[:3]
        remaining = jobs[3:]
        if top:
            sections.append((f"⭐ Top {name}", top))
        top_remaining[name] = remaining

    # Top 3 other
    other_top = other_jobs[:3]
    other_remaining = other_jobs[3:]
    if other_top:
        sections.append(("⭐ Top Other Jobs", other_top))

    # Remaining per location
    for name, _ in LOCATION_BUCKETS:
        if top_remaining[name]:
            sections.append((f"More {name}", top_remaining[name]))

    # Remaining other
    if other_remaining:
        sections.append(("More Other Jobs", other_remaining))

    return sections


def _build_job_html(scored: ScoredJob) -> str:
    job = scored.job
    date_posted = _format_date(job.date_posted)
    return f"""
    <tr>
      <td style="padding:12px; border-bottom:1px solid #eee;">
        <strong><a href="{job.url}">{job.title}</a></strong><br>
        {job.company} &middot; {job.location}<br>
        <small>Remote: {job.remote or 'N/A'} &middot; Salary: {_format_salary(job)} &middot; Posted: {date_posted}</small><br>
        <span style="color:#2563eb; font-weight:bold;">Score: {scored.score}/100</span><br>
        <em>{scored.rationale}</em>
      </td>
    </tr>"""


def send_notification(to_email: str, scored_jobs: list[ScoredJob]) -> None:
    """Send an email digest of high-scoring jobs, organized by location."""
    if not scored_jobs:
        logger.info("No jobs above threshold — skipping email.")
        return

    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    sections = _categorize_jobs(scored_jobs)

    sections_html = ""
    for section_title, section_jobs in sections:
        rows = "\n".join(_build_job_html(sj) for sj in section_jobs)
        sections_html += f"""
  <h3 style="margin-top:24px; padding-bottom:4px; border-bottom:2px solid #2563eb;">
    {section_title} ({len(section_jobs)})
  </h3>
  <table style="width:100%; border-collapse:collapse;">
    {rows}
  </table>"""

    html = f"""\
<html>
<body style="font-family: sans-serif; max-width: 700px; margin: auto;">
  <h2>Job Scout: {len(scored_jobs)} New Match{"es" if len(scored_jobs) != 1 else ""}</h2>
  {sections_html}
  <p style="color:#888; font-size:12px; margin-top:24px;">
    Sent by <a href="https://github.com/doughavlik/job-scout-agent">Job Scout Agent</a>
  </p>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Job Scout: {len(scored_jobs)} new match{'es' if len(scored_jobs) != 1 else ''}"
    msg["From"] = sender
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    logger.info("Sending email to %s with %d jobs", to_email, len(scored_jobs))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, to_email, msg.as_string())
    logger.info("Email sent successfully.")

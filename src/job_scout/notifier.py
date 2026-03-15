"""Email notifications via Gmail SMTP with App Password."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .models import ScoredJob

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _format_salary(job) -> str:
    if job.salary_min and job.salary_max:
        return f"{job.salary_currency} {job.salary_min:,.0f} – {job.salary_max:,.0f}"
    if job.salary_min:
        return f"{job.salary_currency} {job.salary_min:,.0f}+"
    if job.salary_max:
        return f"Up to {job.salary_currency} {job.salary_max:,.0f}"
    return "Not listed"


def _build_job_html(scored: ScoredJob) -> str:
    job = scored.job
    return f"""
    <tr>
      <td style="padding:12px; border-bottom:1px solid #eee;">
        <strong><a href="{job.url}">{job.title}</a></strong><br>
        {job.company} &middot; {job.location}<br>
        <small>Remote: {job.remote or 'N/A'} &middot; Salary: {_format_salary(job)}</small><br>
        <span style="color:#2563eb; font-weight:bold;">Score: {scored.score}/100</span><br>
        <em>{scored.rationale}</em>
      </td>
    </tr>"""


def send_notification(to_email: str, scored_jobs: list[ScoredJob]) -> None:
    """Send an email digest of high-scoring jobs."""
    if not scored_jobs:
        logger.info("No jobs above threshold — skipping email.")
        return

    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    rows = "\n".join(_build_job_html(sj) for sj in scored_jobs)
    html = f"""\
<html>
<body style="font-family: sans-serif; max-width: 600px; margin: auto;">
  <h2>Job Scout: {len(scored_jobs)} New Match{"es" if len(scored_jobs) != 1 else ""}</h2>
  <table style="width:100%; border-collapse:collapse;">
    {rows}
  </table>
  <p style="color:#888; font-size:12px; margin-top:24px;">
    Sent by <a href="https://github.com/your-user/job-scout-agent">Job Scout Agent</a>
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

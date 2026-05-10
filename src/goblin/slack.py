import os
import httpx
from typing import List, Dict


def job_to_blocks(job, score: float | None = None):
    line2 = f"{job.location}  ·  _{job.source}_"
    if score is not None:
        line2 = f"Score: *{score:.1f}*  ·  {line2}"

    meta: list[str] = []
    if getattr(job, "category", None):
        meta.append(job.category)
    if getattr(job, "job_type", None):
        meta.append(job.job_type)
    if getattr(job, "salary", None):
        meta.append(job.salary)
    if getattr(job, "published_at", None):
        meta.append(job.published_at.split("T")[0])
    tags = getattr(job, "tags", []) or []
    if tags:
        meta.append(", ".join(tags[:3]))

    detail_lines = [line2]
    if meta:
        detail_lines.append(" • ".join(meta))

    header = f"*<{job.url}|{job.title}>*  ·  {job.company}"
    text = header + "\n" + "\n".join(detail_lines)
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}}
    ]


async def post_blocks(
    blocks: List[Dict],
    text: str = "New jobs",
    channel_override: str | None = None,
):
    token = os.environ.get("GOBLIN_SLACK_BOT_TOKEN")
    channel = channel_override or os.environ.get("GOBLIN_SLACK_CHANNEL")
    if not (token and channel):
        raise RuntimeError("Missing Slack env vars.")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "channel": channel,
                "text": text,
                "blocks": blocks,
            },
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data}")

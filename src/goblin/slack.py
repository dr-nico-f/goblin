import os, httpx, asyncio
from typing import List, Dict
from goblin.model import Job

async def post_to_slack(text: str):
    token = os.environ.get("GOBLIN_SLACK_BOT_TOKEN")
    channel = os.environ.get("GOBLIN_SLACK_CHANNEL")
    if not (token and channel):
        raise RuntimeError("Missing Slack env vars.")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json; charset=utf-8"},
            json={"channel": channel, "text": text},
        )
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data}")

def job_to_blocks(job, score: float | None = None):
    line2 = f"{job.location}  ·  _{job.source}_"
    if score is not None:
        line2 = f"Score: *{score:.1f}*  ·  {line2}"
    return [
        {"type":"section","text":{"type":"mrkdwn",
         "text": f"*<{job.url}|{job.title}>*  ·  {job.company}\n{line2}"}}
    ]

async def post_blocks(blocks: List[Dict], text: str = "New jobs"):
    token = os.environ.get("GOBLIN_SLACK_BOT_TOKEN")
    channel = os.environ.get("GOBLIN_SLACK_CHANNEL")
    if not (token and channel):
        raise RuntimeError("Missing Slack env vars.")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json; charset=utf-8"},
            json={"channel": channel, "text": text, "blocks": blocks},
        )
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data}")
"""
AWS Lambda entrypoint for Goblin.

Reads Slack creds from environment variables (not .env),
runs the same fetch → filter → rank → dedup → post pipeline
using your existing modules.
"""

import os
import json
from goblin.filters import load_filters, matches
from goblin.rank import load_weights, score as score_job
from goblin.dedup import load_seen, save_seen, fingerprint
from goblin.slack import post_blocks, job_to_blocks
from goblin.collectors.remotive import fetch_remotive
from goblin.config import load_sources

# Optional: tiny helper to format a response
def _resp(status: int, body: dict):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}

def lambda_handler(event, context):
    # Sanity checks (Lambda will use real env vars, not .env)
    token = os.getenv("GOBLIN_SLACK_BOT_TOKEN")
    channel = os.getenv("GOBLIN_SLACK_CHANNEL")
    if not token or not channel:
        # Fail clearly so CloudWatch shows a useful error
        return _resp(500, {"error": "Missing Slack env vars: GOBLIN_SLACK_BOT_TOKEN or GOBLIN_SLACK_CHANNEL"})

    # Source defaults from config, allow override via event
    sources_cfg = load_sources().get("sources", {})
    source = (event or {}).get("source", "remotive")
    cfg = sources_cfg.get(source, {})
    if not cfg.get("enabled", True):
        return _resp(200, {"message": f"Source '{source}' disabled in config"})

    limit    = int((event or {}).get("limit", cfg.get("limit", 25)))
    category = (event or {}).get("category", cfg.get("category", "software-dev"))
    query    = (event or {}).get("query", cfg.get("query", ""))

    # Fetch
    jobs = []
    if source == "remotive":
        jobs = fetch_remotive(category=category, query=query, limit=limit)
    elif source == "stub":
        from goblin.fetch import fetch_stub
        jobs = fetch_stub()
    else:
        return _resp(400, {"error": f"Unknown source '{source}'"})

    # Filter + score
    filters = load_filters()
    weights = load_weights()
    matched = [j for j in jobs if matches(j, filters)]
    scored = [(score_job(j, filters, weights), j) for j in matched]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Dedup
    seen = load_seen()
    new = []
    for s, j in scored:
        fp = fingerprint(j.title, j.company, j.url)
        if fp not in seen:
            new.append((s, j))

    if not new:
        return _resp(200, {"message": "Nothing new to post", "fetched": len(jobs), "matched": len(matched), "new": 0})

    # Build Slack blocks
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"Goblin: {source} matches"}}]
    for s, j in new:
        blocks.extend(job_to_blocks(j, s))
        blocks.append({"type": "divider"})

    # Post (async helper works fine inside Lambda)
    import asyncio
    asyncio.run(post_blocks(blocks, text=f"Goblin {source} update"))

    # Persist new fingerprints (no-op in Lambda unless you later swap to DynamoDB)
    for _, j in new:
        seen.add(fingerprint(j.title, j.company, j.url))
    save_seen(seen)

    return _resp(200, {"message": f"Posted {len(new)} new match(es)", "fetched": len(jobs), "matched": len(matched), "new": len(new)})
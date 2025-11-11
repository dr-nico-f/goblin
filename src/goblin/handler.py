"""
AWS Lambda entrypoint for Goblin (multi-profile).

Reads Slack creds from environment variables (not .env) and runs:
fetch → filter → rank → dedup → post, using per-profile configs.
"""

import os
import json
import asyncio
from goblin.config import load_sources
from goblin.profiles import get_profile
from goblin.filters import load_filters, matches
from goblin.rank import load_weights, score as score_job
from goblin.dedup import load_seen, save_seen, fingerprint
from goblin.slack import post_blocks, job_to_blocks
from goblin.collectors.remotive import fetch_remotive
from goblin.fetch import fetch_stub

def _resp(status: int, body: dict):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}

def lambda_handler(event, context):
    event = event or {}

    # Require Slack token; channel comes from profile config
    token = os.getenv("GOBLIN_SLACK_BOT_TOKEN")
    if not token:
        return _resp(500, {"error": "Missing env var GOBLIN_SLACK_BOT_TOKEN"})

    # Profile (e.g., "nick", "nina")
    profile = event.get("profile", "nick")
    prof = get_profile(profile)
    if not prof:
        return _resp(400, {"error": f"Unknown profile '{profile}'"})

    channel_id = prof.get("channel")
    if not channel_id:
        return _resp(500, {"error": f"Profile '{profile}' missing 'channel' in profiles.yaml"})

    # Per-profile config paths + cache path
    filt_path  = prof.get("filters", "configs/filters.yaml")
    rank_path  = prof.get("ranking", "configs/ranking.yaml")
    cache_path = os.path.join("data", profile, "posted.json")

    # Source & defaults (from sources.yaml), allow event overrides
    source = event.get("source", "remotive")
    sources_cfg = load_sources().get("sources", {})
    scfg = sources_cfg.get(source, {})
    limit    = int(event.get("limit", scfg.get("limit", 25)))
    category = event.get("category", scfg.get("category", "software-dev"))
    query    = event.get("query", scfg.get("query", ""))

    # Fetch
    if source == "remotive":
        jobs = fetch_remotive(category=category, query=query, limit=limit)
    elif source == "stub":
        jobs = fetch_stub()
    else:
        return _resp(400, {"error": f"Unknown source '{source}'"})

    # Filter + score
    filters = load_filters(filt_path)
    weights = load_weights(rank_path)
    matched = [j for j in jobs if matches(j, filters)]
    scored = [(score_job(j, filters, weights), j) for j in matched]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Dedup per profile
    seen = load_seen(cache_path)
    new = []
    for s, j in scored:
        fp = fingerprint(j.title, j.company, j.url)
        if fp not in seen:
            new.append((s, j))

    if not new:
        return _resp(200, {"message": "Nothing new to post", "profile": profile,
                           "fetched": len(jobs), "matched": len(matched), "new": 0})

    # Build Slack blocks (include score)
    blocks = [{"type": "header", "text": {"type": "plain_text",
              "text": f"Goblin: {source} matches ({profile})"}}]
    for s, j in new:
        blocks.extend(job_to_blocks(j, s))
        blocks.append({"type": "divider"})

    # Post to the profile's channel (slack.post_blocks supports channel_override)
    asyncio.run(post_blocks(blocks, text=f"Goblin {source} update ({profile})",
                            channel_override=channel_id))

    # Persist fingerprints (local JSON now; DynamoDB later)
    for _, j in new:
        seen.add(fingerprint(j.title, j.company, j.url))
    save_seen(cache_path, seen)

    return _resp(200, {"message": f"Posted {len(new)} new match(es)",
                       "profile": profile, "fetched": len(jobs),
                       "matched": len(matched), "new": len(new)})

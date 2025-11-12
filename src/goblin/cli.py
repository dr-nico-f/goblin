import asyncio, click, os, sys
from dotenv import load_dotenv
from goblin.util.log import setup_logging
from goblin.slack import post_blocks, job_to_blocks
from goblin.filters import load_filters, matches
from goblin.fetch import fetch_stub
from goblin.dedup import load_seen, save_seen, fingerprint


# Load .env before anything else
load_dotenv()

# Initialize rotating logger
log = setup_logging()

def require_env(var):
    v = os.environ.get(var)
    if not v:
        click.echo(f"[ERROR] Missing env var: {var}", err=True)
        sys.exit(1)
    return v

@click.group()
def cli():
    """Goblin command-line interface."""
    pass

DEFAULT_LIMIT = 10

@cli.command()
@click.option("--source", default="stub", type=click.Choice(["stub","remotive"]), show_default=True)
@click.option("--limit", type=int, default=None, help=f"Max jobs to fetch (falls back to config or {DEFAULT_LIMIT})")
@click.option("--dry-run", is_flag=True)
@click.option("--profile", default="nick", show_default=True, help="Profile name from configs/profiles.yaml")
def find(source, limit, dry_run, profile):
    from goblin.config import load_sources
    from goblin.profiles import get_profile
    from goblin.filters import load_filters, matches
    from goblin.rank import load_weights, score as score_job
    from goblin.dedup import load_seen, save_seen, fingerprint, cache_file
    from goblin.collectors.remotive import fetch_remotive
    from goblin.fetch import fetch_stub
    from goblin.slack import post_blocks, job_to_blocks
    import asyncio, click, os

    prof = get_profile(profile)
    if not prof:
        click.echo(f"[ERROR] unknown profile '{profile}'"); return

    # paths / channel from profile
    filt_path   = prof.get("filters", "configs/filters.yaml")
    rank_path   = prof.get("ranking", "configs/ranking.yaml")
    channel_id  = prof.get("channel")  # required
    if not channel_id:
        click.echo(f"[ERROR] profile '{profile}' missing 'channel' in configs/profiles.yaml"); return
    cache_path = cache_file(profile)   # was os.path.join("data", profile, "posted.json")

    sources_cfg = load_sources().get("sources", {})
    cfg = sources_cfg.get(source, {})
    cfg_limit = cfg.get("limit", DEFAULT_LIMIT)
    limit = limit if limit is not None else cfg_limit

    log.info("profile=%s channel=%s source=%s limit=%s", profile, channel_id, source, limit)

    # fetch
    if source == "remotive":
        category = cfg.get("category", "software-dev"); query = cfg.get("query", "")
        click.echo(f"[INFO] fetching Remotive (limit={limit}, category={category}, query='{query}')")
        jobs = fetch_remotive(category=category, query=query, limit=limit)
    else:
        click.echo(f"[INFO] using stub source (limit={limit})")
        jobs = fetch_stub()

    # filter + score
    filters = load_filters(filt_path)
    weights = load_weights(rank_path)
    matched = [j for j in jobs if matches(j, filters)]
    log.info("fetched=%d matched=%d", len(jobs), len(matched))

    scored = [(score_job(j, filters, weights), j) for j in matched]
    scored.sort(key=lambda x: x[0], reverse=True)

    # dedup per profile
    seen = load_seen(cache_path)
    new = []
    for s, j in scored:
        fp = fingerprint(j.title, j.company, j.url)
        if fp not in seen:
            new.append((s, j))

    click.echo(f"[INFO] new={len(new)} already_posted={len(scored)-len(new)}")
    log.info("new=%d already_posted=%d", len(new), len(scored) - len(new))

    if dry_run:
        for s, j in new:
            click.echo(f"{s:>4.1f}  {j.title} · {j.company} · {j.location}")
        return
    if not new:
        click.echo("[INFO] nothing new to post"); return

    blocks = [{"type":"header","text":{"type":"plain_text","text":f"Goblin: {source} matches ({profile})"}}]
    for s, j in new:
        blocks.extend(job_to_blocks(j, s))
        blocks.append({"type":"divider"})

    asyncio.run(post_blocks(blocks, text=f"Goblin {source} update ({profile})", channel_override=channel_id))
    click.echo(f"[OK] Posted {len(new)} new match(es) to {channel_id} for profile '{profile}'")
    for _, j in new:
        seen.add(fingerprint(j.title, j.company, j.url))
    save_seen(cache_path, seen)

@cli.command(name="pull-remotive")
@click.option("--q", "query", default="", help="Search query")
@click.option("--category", default="software-dev", show_default=True, help="Remotive category")
@click.option("--limit", default=10, show_default=True, help="Max jobs to show")
def pull_remotive(query, category, limit):
    """Fetch jobs from Remotive and print titles (no posting)."""
    from goblin.collectors.remotive import fetch_remotive
    from goblin.filters import load_filters, matches

    jobs = fetch_remotive(query=query, category=category, limit=limit)
    f = load_filters()
    matched = [j for j in jobs if matches(j, f)]
    click.echo(f"[INFO] fetched={len(jobs)} matched={len(matched)}")
    for j in matched:
        click.echo(f" - {j.title} · {j.company} · {j.location}")

@cli.command(name="score-remotive")
@click.option("--limit", default=10, show_default=True)
def score_remotive(limit):
    """Fetch Remotive, score matches, print top results (no posting)."""
    from goblin.collectors.remotive import fetch_remotive
    from goblin.filters import load_filters, matches
    from goblin.rank import load_weights, score

    filters = load_filters()
    weights = load_weights()
    jobs = [j for j in fetch_remotive(category="software-dev", limit=limit) if matches(j, filters)]
    scored = [(score(j, filters, weights), j) for j in jobs]
    scored.sort(reverse=True, key=lambda x: x[0])

    click.echo(f"[INFO] matched={len(scored)}")
    for s, j in scored:
        click.echo(f"{s:>4.1f}  {j.title} · {j.company} · {j.location}")

@cli.command()
@click.option("--message", default="Goblin test ✅", show_default=True)
def test(message):
    """Post a simple health-check message and one fake job card to Slack."""
    import asyncio
    from goblin.model import Job
    from goblin.slack import post_blocks, job_to_blocks

    j = Job(
        id="healthcheck-1",
        title="Health Check: Backend Engineer (Python/AWS)",
        company="Goblin Labs",
        location="Remote — Anywhere",
        url="https://example.com/healthcheck",
        source="test",
    )
    blocks = [{"type":"header","text":{"type":"plain_text","text":message}}]
    blocks += job_to_blocks(j, 9.9)  # show score if your job_to_blocks supports it
    asyncio.run(post_blocks(blocks, text=message))
    click.echo("[OK] Test post sent.")

if __name__ == "__main__":
    cli()
    
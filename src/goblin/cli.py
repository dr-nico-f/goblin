import asyncio, click, os
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

@cli.command()
@click.option("--source", default="stub", type=click.Choice(["stub", "remotive"]), show_default=True)
@click.option("--limit", default=10, show_default=True, help="Max jobs per source")
@click.option("--dry-run", is_flag=True, help="Print matches instead of posting")
def find(source, limit, dry_run):
    """Fetch -> filter -> post."""
    from goblin.filters import load_filters, matches
    from goblin.fetch import fetch_stub
    from goblin.collectors.remotive import fetch_remotive
    from goblin.slack import post_blocks, job_to_blocks
    from goblin.rank import load_weights, score as score_job
    from goblin.dedup import load_seen, save_seen, fingerprint
    import asyncio, click

    filters = load_filters()

    log.info("source=%s limit=%s", source, limit)
    if source == "remotive":
        click.echo(f"[INFO] fetching Remotive (limit={limit})")
        jobs = fetch_remotive(category="software-dev", limit=limit)
    else:
        click.echo("[INFO] using stub source")
        jobs = fetch_stub()

    matched = [j for j in jobs if matches(j, filters)]
    log.info("fetched=%d matched=%d", len(jobs), len(matched))

    weights = load_weights()
    scored = [(score_job(j, filters, weights), j) for j in matched]
    scored.sort(key=lambda x: x[0], reverse=True)

    # dedup against scored list
    seen = load_seen()
    new = []
    for s, j in scored:
        fp = fingerprint(j.title, j.company, j.url)
        if fp not in seen:
            new.append((s, j))

    click.echo(f"[INFO] new={len(new)} already_posted={len(scored) - len(new)}")
    log.info("new=%d already_posted=%d", len(new), len(scored) - len(new))

    if dry_run:
        for s, j in new:
            click.echo(f"{s:>4.1f}  {j.title} · {j.company} · {j.location}")
        return

    if not new:
        click.echo("[INFO] nothing new to post")
        return

    # build blocks from `new` not `matched`
    blocks = [{"type":"header","text":{"type":"plain_text","text":f"Goblin: {source} matches"}}]
    for s, j in new:
        blocks.extend(job_to_blocks(j, s))
        blocks.append({"type":"divider"})

    # post
    try:
        asyncio.run(post_blocks(blocks, text=f"Goblin {source} update"))
        click.echo(f"[OK] Posted {len(new)} new match(es) from {source}")
        log.info("posted=%d new matches from %s", len(new), source)
    except Exception as e:
        log.exception("Slack post failed: %s", e)
        raise

    # remember what we posted
    for _, j in new:
        seen.add(fingerprint(j.title, j.company, j.url))
    save_seen(seen)

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

if __name__ == "__main__":
    cli()
    
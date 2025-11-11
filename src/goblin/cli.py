import os
import sys
import asyncio
import click
from goblin.slack import post_blocks, job_to_blocks
from goblin.filters import load_filters, matches
from goblin.fetch import fetch_stub

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
    import asyncio, sys, click, os

    filters = load_filters()

    if source == "remotive":
        click.echo(f"[INFO] fetching Remotive (limit={limit})")
        jobs = fetch_remotive(category="software-dev", limit=limit)
    else:
        click.echo("[INFO] using stub source")
        jobs = fetch_stub()

    matched = [j for j in jobs if matches(j, filters)]
    click.echo(f"[INFO] fetched={len(jobs)} matched={len(matched)}")

    if dry_run:
        for j in matched:
            click.echo(f" - {j.title} · {j.company} · {j.location}")
        return

    if not matched:
        click.echo("[INFO] no matches to post")
        return

    # build Slack blocks
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"Goblin: {source} matches"}}]
    for j in matched:
        blocks.extend(job_to_blocks(j))
        blocks.append({"type": "divider"})

    # post
    try:
        asyncio.run(post_blocks(blocks, text=f"Goblin {source} update"))
        click.echo(f"[OK] Posted {len(matched)} match(es) from {source}")
    except Exception as e:
        click.echo(f"[ERROR] Slack post failed: {e}", err=True)
        sys.exit(2)

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


if __name__ == "__main__":
    cli()
    
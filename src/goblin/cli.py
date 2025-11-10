import asyncio, click
from goblin.slack import post_to_slack, post_blocks, job_to_blocks
from goblin.model import Job

@click.group()
def cli(): pass

@cli.command()
@click.argument("message", required=False, default="Goblin reporting in 🧙‍♂️")
def run(message):
    asyncio.run(post_to_slack(message))
    print("Message sent.")

@cli.command()
def demo():
    """Post one stub job with Slack blocks."""
    j = Job(
        id="stub-1",
        title="Backend Software Engineer (Python/AWS)",
        company="Orbital Co",
        location="Remote — United States",
        url="https://example.com/jobs/1",
    )
    blocks = job_to_blocks(j)
    asyncio.run(post_blocks(blocks, text="Goblin demo"))
    print("Demo job posted.")
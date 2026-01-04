# Goblin 🧙‍♂️  
**Automated Job Discovery Bot**

Goblin fetches new remote job listings, filters and ranks them by your criteria, and posts the best matches directly to Slack.  
Built with **Python 3.10+**, **AWS**, and the **Slack API**.

---

## 🚀 Features
- 🔍 Live job fetching from [Remotive](https://remotive.com/api/remote-jobs)
- 🧩 Keyword, title, and location filters via YAML configs
- ⚖️ Ranking system with customizable weights
- 🧠 Deduplication to prevent reposts
- 🪵 Rotating log files for all runs
- 🔐 `.env`-based secrets loading (no manual exports)
- 🧪 Health-check command to verify Slack connectivity
- 🧾 Rich Slack cards (job type, salary, publish date, tags when available)
- 🏗️ Modular design ready for AWS Lambda + EventBridge automation

---

## 🧱 Project Structure
```
src/goblin/
  cli.py              → Main CLI interface
  collectors/         → Job source modules (Remotive, etc.)
  config.py           → Loads YAML configuration files
  dedup.py            → Local cache to avoid duplicate posts
  filters.py          → Job filtering logic
  rank.py             → Scoring and ranking
  slack.py            → Slack posting functions
  util/log.py         → Rotating file and console logging

configs/
  filters.yaml        → Filter rules for job titles, keywords, locations
  ranking.yaml        → Scoring weights
  sources.yaml        → Source defaults and limits

data/
  posted.json         → Local dedup cache

logs/
  goblin.log          → Rotating runtime logs
```

---

## ⚙️ Setup

### 1. Clone and create a virtual environment
```bash
git clone https://github.com/<your-username>/goblin.git
cd goblin
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

*(Optional)* Install the package in editable mode so you can skip setting `PYTHONPATH` for every command:
```bash
pip install -e src
```

### 2. Environment variables  
Create a file named `.env` in the project root:
```
GOBLIN_SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
GOBLIN_SLACK_CHANNEL=C0123456789
```

*(Keep this file private — it’s already ignored by `.gitignore`.)*

---

## 🧠 Usage

### Slack slash command handler (new)
Deploy `goblin.slack_events.lambda_handler` behind an HTTPS endpoint (e.g., API Gateway) configured as a Slack Slash Command request URL.  
Env vars required: `SLACK_SIGNING_SECRET`, `GOBLIN_SLACK_BOT_TOKEN` (for posting elsewhere).  
Commands (extendable in `src/goblin/commands.py`):
- `help`
- `status [--profile nick]`
- `filters salary [--profile nick]`
- `filters show [--profile nick]`
- `filters set salary <min> [--allow-missing true|false] [--profile nick]`
- `profiles list`
- `sources list`
- `sources set <source> (enabled|query|category|limit) <value>`
- `run [--profile nick] [--source remotive] [--limit N]`
- `run --preview` (dry-run; no Slack post, prints top matches)
- `schedule show|set` (now backed by EventBridge via `GOBLIN_SCHEDULE_RULE`)

### Dry run (no Slack post)
```bash
PYTHONPATH=$PWD/src python -m goblin.cli find --source remotive --dry-run
```

### Real run (posts to Slack)
```bash
PYTHONPATH=$PWD/src python -m goblin.cli find --source remotive
```

### Health check
```bash
PYTHONPATH=$PWD/src python -m goblin.cli test
```

Tip: override the default fetch limit for an ad-hoc run with `--limit`, e.g. `--limit 5`.
If you installed with `pip install -e src`, you can omit the `PYTHONPATH=$PWD/src` prefix in the examples above.

### Logs
All runs are logged to `logs/goblin.log`.

---

## 🧩 Configuration

### Filters (`configs/filters.yaml`)
Control which titles, keywords, and locations Goblin includes or excludes.
You can also add optional salary gating, e.g.:
```
salary:
  min: 140000          # rejects jobs whose lower-bound salary is below this
  allow_missing: false # set true to keep jobs without a salary listed
```
Filters are now stored remotely when `GOBLIN_FILTERS_BUCKET` is set (S3). Env vars:
- `GOBLIN_FILTERS_BUCKET`: S3 bucket for per-profile filter YAML (key: `<prefix>/<profile>.yaml`)
- `GOBLIN_FILTERS_PREFIX`: optional key prefix (default: `filters`)

### Ranking (`configs/ranking.yaml`)
Adjust the weight of keyword hits, title matches, remote bonuses, and penalties.

### Sources (`configs/sources.yaml`)
Enable or disable job sources and set default categories, limits, and queries.

### Scheduling
Slack command `schedule set <expr>` updates the EventBridge rule in `GOBLIN_SCHEDULE_RULE`.
Supply cron as `cron(...)` or plain 5/6-field cron (auto-wrapped). Requires IAM permissions for `events:DescribeRule` and `events:PutRule`.

---

## 🧪 Development Notes
- Requires **Python 3.10+**
- Uses `httpx`, `click`, `pyyaml`, and `python-dotenv`
- Tested locally with virtualenv and Slack bot tokens
- Logs and local caches are ignored via `.gitignore`

---

## ☁️ AWS Deployment (coming soon)
Goblin is designed to run serverlessly on **AWS Lambda** with a daily schedule via **EventBridge**.  
Planned features:
- GitHub Actions for automatic Lambda deployment  
- Secrets stored in AWS Parameter Store or Secrets Manager  
- Optional DynamoDB dedup cache  

---

## 📜 License
MIT © 2025 — Goblin Labs  
Created by [Nico](https://github.com/dr-nico-f)

---

> 🧙 *“A good bot posts once. A great bot never reposts.”*
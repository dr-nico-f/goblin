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

### 2. Environment variables  
Create a file named `.env` in the project root:
```
GOBLIN_SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
GOBLIN_SLACK_CHANNEL=C0123456789
```

*(Keep this file private — it’s already ignored by `.gitignore`.)*

---

## 🧠 Usage

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

### Logs
All runs are logged to `logs/goblin.log`.

---

## 🧩 Configuration

### Filters (`configs/filters.yaml`)
Control which titles, keywords, and locations Goblin includes or excludes.

### Ranking (`configs/ranking.yaml`)
Adjust the weight of keyword hits, title matches, remote bonuses, and penalties.

### Sources (`configs/sources.yaml`)
Enable or disable job sources and set default categories, limits, and queries.

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
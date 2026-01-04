"""
Lightweight command parsing for Slack slash commands or mentions.

Current commands (extendable):
  - help
  - status [--profile PROFILE]
  - run [--profile PROFILE] [--source remotive|stub] [--limit N]
  - filters show [--profile PROFILE]
  - filters salary [--profile PROFILE]                # view salary filter
  - filters set salary <min> [--allow-missing true|false] [--profile PROFILE]
  - profiles list
  - sources list
  - schedule show
  - schedule set <expr>   (stub; informational only)
"""

import asyncio
import os
from dataclasses import dataclass
from typing import List, Optional

import yaml

from goblin.collectors.remotive import fetch_remotive
from goblin.config import load_sources
from goblin.dedup import cache_file, fingerprint, load_seen, save_seen
from goblin.fetch import fetch_stub
from goblin.filter_store import load_profile_filters, save_profile_filters
from goblin.filters import matches
from goblin.profiles import get_profile, load_profiles
from goblin.rank import load_weights, score as score_job
from goblin.schedule import ScheduleError, get_schedule, set_schedule
from goblin.slack import job_to_blocks, post_blocks


@dataclass
class CommandResult:
    text: str
    blocks: Optional[List[dict]] = None
    status: int = 200


def _get_profile_name(args: List[str], default: str = "nick") -> str:
    if "--profile" in args:
        idx = args.index("--profile")
        if idx + 1 < len(args):
            return args[idx + 1]
    return default


def _format_salary_info(filters: dict) -> str:
    salary_cfg = filters.get("salary", {}) or {}
    min_salary = salary_cfg.get("min")
    allow_missing = bool(salary_cfg.get("allow_missing", False))
    if min_salary is None:
        return "Salary filter: not set"
    return (
        "Salary filter: "
        f"min=${min_salary:,} "
        f"(allow_missing={allow_missing})"
    )


def _fmt_list(title: str, items: list) -> str:
    if not items:
        return f"*{title}*: (none)"
    return f"*{title}*: {', '.join(items)}"


def _get_source_args(args: List[str], sources_cfg: dict) -> tuple[str, dict]:
    source = "remotive"
    if "--source" in args:
        idx = args.index("--source")
        if idx + 1 < len(args):
            source = args[idx + 1]
    scfg = sources_cfg.get(source, {})
    limit = scfg.get("limit", 10)
    if "--limit" in args:
        idx = args.index("--limit")
        if idx + 1 < len(args):
            try:
                limit = int(args[idx + 1])
            except ValueError:
                pass
    return source, {"limit": limit, **scfg}


def command_help() -> CommandResult:
    lines = [
        "*Goblin Slack commands*",
        "• `help` — show this message",
        "• `status [--profile nick]` — source + salary filter info",
        "• `run [--profile nick] [--source remotive] [--limit N]` — "
        "fetch/post now",
        "• `filters show [--profile nick]` — show all filters for profile",
        "• `filters salary [--profile nick]` — show salary filter",
        "• `filters set salary <min> [--allow-missing true|false] "
        "[--profile nick]`",
        "• `profiles list` — list available profiles",
        "• `sources list` — list configured sources",
        "• `schedule show|set` — view or note schedule (stub)",
    ]
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        }
    ]
    return CommandResult(text="\n".join(lines), blocks=blocks)


def command_status(args: List[str]) -> CommandResult:
    profile_name = _get_profile_name(args)
    prof = get_profile(profile_name)
    if not prof:
        return CommandResult(
            text=f"Unknown profile `{profile_name}`",
            status=400,
        )

    sources_cfg = load_sources().get("sources", {})
    remotive_cfg = sources_cfg.get("remotive", {})
    filt_path = prof.get("filters", "configs/filters.yaml")
    filters = load_profile_filters(profile_name, filt_path)

    lines = [
        f"*Profile*: {profile_name}",
        f"*Channel*: {prof.get('channel', 'unset')}",
        "*Default source*: remotive "
        f"(limit={remotive_cfg.get('limit', 'n/a')}, "
        f"category={remotive_cfg.get('category', 'n/a')}, "
        f"query='{remotive_cfg.get('query', '')}')",
        _format_salary_info(filters),
    ]
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Goblin status"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        },
    ]
    return CommandResult(text="\n".join(lines), blocks=blocks)


def command_filters_salary(args: List[str]) -> CommandResult:
    profile_name = _get_profile_name(args)
    prof = get_profile(profile_name)
    if not prof:
        return CommandResult(
            text=f"Unknown profile `{profile_name}`",
            status=400,
        )
    filt_path = prof.get("filters", "configs/filters.yaml")
    filters = load_profile_filters(profile_name, filt_path)
    txt = _format_salary_info(filters)
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Profile*: {profile_name}\n{txt}",
            },
        }
    ]
    return CommandResult(text=txt, blocks=blocks)


def command_filters_show(args: List[str]) -> CommandResult:
    profile_name = _get_profile_name(args)
    prof = get_profile(profile_name)
    if not prof:
        return CommandResult(
            text=f"Unknown profile `{profile_name}`",
            status=400,
        )
    filt_path = prof.get("filters", "configs/filters.yaml")
    filters = load_profile_filters(profile_name, filt_path)
    titles = filters.get("titles", {}) or {}
    keywords = filters.get("keywords", {}) or {}
    locations = filters.get("locations", {}) or {}
    parts = [
        f"*Profile*: {profile_name}",
        _fmt_list("Titles include", titles.get("include") or []),
        _fmt_list("Titles exclude", titles.get("exclude") or []),
        _fmt_list("Keywords include", keywords.get("include") or []),
        _fmt_list("Keywords exclude", keywords.get("exclude") or []),
        _fmt_list("Locations include", locations.get("include") or []),
        _fmt_list("Locations exclude", locations.get("exclude") or []),
        _format_salary_info(filters),
    ]
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Filters: {profile_name}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(parts)},
        },
    ]
    return CommandResult(text="\n".join(parts), blocks=blocks)


def _parse_bool(val: str) -> bool:
    return str(val).lower() in ("1", "true", "yes", "y", "on")


def _has_flag(args: List[str], flag: str) -> bool:
    return flag in args


def _load_sources_file(path: str = "configs/sources.yaml") -> dict:
    if not os.path.exists(path):
        return {"sources": {}}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"sources": {}}


def _save_sources_file(data: dict, path: str = "configs/sources.yaml") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _get_rule_name(args: List[str], profile: str) -> str:
    """Resolve rule name from --rule flag, profile config, or env default."""
    if "--rule" in args:
        idx = args.index("--rule")
        if idx + 1 < len(args):
            return args[idx + 1]
    prof = get_profile(profile)
    if prof and prof.get("schedule_rule"):
        return prof["schedule_rule"]
    env_rule = os.environ.get("GOBLIN_SCHEDULE_RULE")
    if env_rule:
        return env_rule
    raise ScheduleError(
        "No schedule rule provided. Use --rule or set schedule_rule in "
        "profile or GOBLIN_SCHEDULE_RULE."
    )


def command_filters_set_salary(args: List[str]) -> CommandResult:
    profile_name = _get_profile_name(args)
    prof = get_profile(profile_name)
    if not prof:
        return CommandResult(
            text=f"Unknown profile `{profile_name}`",
            status=400,
        )

    if not args:
        return CommandResult(
            text=(
                "Usage: filters set salary <min> "
                "[--allow-missing true|false]"
            ),
            status=400,
        )

    try:
        min_salary = float(args[0])
    except ValueError:
        return CommandResult(
            text=(
                "Usage: filters set salary <min> "
                "[--allow-missing true|false]"
            ),
            status=400,
        )

    allow_missing = None
    if "--allow-missing" in args:
        idx = args.index("--allow-missing")
        if idx + 1 < len(args):
            allow_missing = _parse_bool(args[idx + 1])
        else:
            return CommandResult(
                text="Invalid value for --allow-missing (use true/false)",
                status=400,
            )
    else:
        # support allow_missing=true syntax
        for tok in args:
            if tok.startswith("allow_missing="):
                allow_missing = _parse_bool(tok.split("=", 1)[1])

    filt_path = prof.get("filters", "configs/filters.yaml")
    data = load_profile_filters(profile_name, filt_path)
    salary_cfg = data.get("salary", {}) or {}
    salary_cfg["min"] = int(min_salary)
    if allow_missing is not None:
        salary_cfg["allow_missing"] = bool(allow_missing)
    data["salary"] = salary_cfg
    save_profile_filters(profile_name, data, filt_path)

    txt = _format_salary_info(data)
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Profile*: {profile_name}\n{txt}",
            },
        }
    ]
    return CommandResult(text=txt, blocks=blocks)


def command_profiles_list() -> CommandResult:
    profiles = (load_profiles().get("profiles") or {}).keys()
    if not profiles:
        return CommandResult(text="No profiles found")
    txt = "Profiles: " + ", ".join(sorted(profiles))
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": txt}}]
    return CommandResult(text=txt, blocks=blocks)


def command_sources_list() -> CommandResult:
    sources_cfg = load_sources().get("sources") or {}
    if not sources_cfg:
        return CommandResult(text="No sources configured")
    parts = []
    for name, cfg in sources_cfg.items():
        parts.append(
            f"{name} (enabled={cfg.get('enabled', True)}, "
            f"limit={cfg.get('limit', 'n/a')}, "
            f"category={cfg.get('category', '')}, "
            f"query='{cfg.get('query', '')}')"
        )
    txt = "\n".join(parts)
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": txt}}]
    return CommandResult(text=txt, blocks=blocks)


def command_sources_set(args: List[str]) -> CommandResult:
    if len(args) < 3:
        return CommandResult(
            text=(
                "Usage: sources set <source> "
                "(enabled|query|category|limit) <value>"
            ),
            status=400,
        )
    name = args[0]
    field = args[1].lower()
    value = " ".join(args[2:])

    path = "configs/sources.yaml"
    data = _load_sources_file(path)
    sources = data.get("sources", {})
    if name not in sources:
        sources[name] = {}
    cfg = sources[name]

    if field == "enabled":
        cfg["enabled"] = _parse_bool(value)
    elif field == "query":
        cfg["query"] = value
    elif field == "category":
        cfg["category"] = value
    elif field == "limit":
        try:
            cfg["limit"] = int(value)
        except ValueError:
            return CommandResult(text="limit must be an integer", status=400)
    else:
        return CommandResult(text=f"Unknown field `{field}`", status=400)

    sources[name] = cfg
    data["sources"] = sources
    _save_sources_file(data, path)
    txt = f"Updated source `{name}`: {field}={value}"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": txt}}]
    return CommandResult(text=txt, blocks=blocks)


def command_schedule_show() -> CommandResult:
    try:
        # default profile if none provided
        rule_name = _get_rule_name([], "nick")
        expr = get_schedule(rule_name)
        if not expr:
            return CommandResult(
                text=f"Schedule not set for rule `{rule_name}`."
            )
        txt = f"Rule `{rule_name}` schedule: `{expr}`"
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": txt}}]
        return CommandResult(text=txt, blocks=blocks)
    except ScheduleError as e:
        return CommandResult(text=str(e), status=400)


def command_schedule_set(args: List[str]) -> CommandResult:
    if not args:
        return CommandResult(
            text="Usage: schedule set <cron expr>",
            status=400,
        )
    expr = args[0]
    try:
        # allow --rule flag after expr; also allow --profile to derive rule
        rest = args[1:]
        profile_name = _get_profile_name(rest)
        rule_name = _get_rule_name(rest, profile_name)
        new_expr = set_schedule(expr, rule_name)
        txt = f"Rule `{rule_name}` updated to `{new_expr}`"
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": txt}}]
        return CommandResult(text=txt, blocks=blocks)
    except ScheduleError as e:
        return CommandResult(text=str(e), status=400)


def command_run(args: List[str]) -> CommandResult:
    profile_name = _get_profile_name(args)
    prof = get_profile(profile_name)
    if not prof:
        return CommandResult(
            text=f"Unknown profile `{profile_name}`",
            status=400,
        )

    sources_cfg = load_sources().get("sources", {})
    source, scfg = _get_source_args(args, sources_cfg)
    preview = _has_flag(args, "--preview")

    channel_id = prof.get("channel")
    if not channel_id:
        return CommandResult(
            text=f"Profile `{profile_name}` missing channel.",
            status=400,
        )

    filt_path = prof.get("filters", "configs/filters.yaml")
    rank_path = prof.get("ranking", "configs/ranking.yaml")
    cache_path = cache_file(profile_name)

    if source == "remotive":
        jobs = fetch_remotive(
            category=scfg.get("category", "software-dev"),
            query=scfg.get("query", ""),
            limit=scfg.get("limit", 10),
        )
    elif source == "stub":
        jobs = fetch_stub()
    else:
        return CommandResult(
            text=f"Unknown source `{source}`",
            status=400,
        )

    filters = load_profile_filters(profile_name, filt_path)
    weights = load_weights(rank_path)
    matched = [j for j in jobs if matches(j, filters)]
    scored = [(score_job(j, filters, weights), j) for j in matched]
    scored.sort(key=lambda x: x[0], reverse=True)

    seen = load_seen(cache_path)
    new = []
    for s, j in scored:
        fp = fingerprint(j.title, j.company, j.url)
        if fp not in seen:
            new.append((s, j))

    if not new:
        return CommandResult(
            text=(
                f"[{profile_name}] Nothing new to post "
                f"(matched={len(matched)})"
            )
        )

    if preview:
        lines = [f"[{profile_name}] Preview (no post)."]
        for s, j in new[:5]:
            lines.append(f"{s:>4.1f}  {j.title} · {j.company} · {j.location}")
        if len(new) > 5:
            lines.append(f"... and {len(new) - 5} more")
        return CommandResult(text="\n".join(lines))

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Goblin: {source} matches ({profile_name})",
            },
        }
    ]
    for s, j in new:
        blocks.extend(job_to_blocks(j, s))
        blocks.append({"type": "divider"})

    asyncio.run(
        post_blocks(
            blocks,
            text=f"Goblin {source} update ({profile_name})",
            channel_override=channel_id,
        )
    )
    for _, j in new:
        seen.add(fingerprint(j.title, j.company, j.url))
    save_seen(cache_path, seen)

    return CommandResult(
        text=(
            f"[{profile_name}] Posted {len(new)} new job(s). "
            f"fetched={len(jobs)} matched={len(matched)} new={len(new)}"
        ),
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"[{profile_name}] Posted {len(new)} new job(s).\n"
                        f"fetched={len(jobs)} matched={len(matched)} "
                        f"new={len(new)}"
                    ),
                },
            }
        ],
    )


def handle_command(text: str) -> CommandResult:
    """
    Very small parser; extend over time with more verbs and subcommands.
    """
    tokens = text.strip().split()
    if not tokens:
        return command_help()

    cmd = tokens[0].lower()
    args = tokens[1:]

    if cmd in ("help", "h", "?"):
        return command_help()

    if cmd == "status":
        return command_status(args)

    if cmd == "run":
        return command_run(args)

    if cmd == "filters" and args:
        sub = args[0].lower()
        sub_args = args[1:]
        if sub == "salary":
            return command_filters_salary(sub_args)
        if sub == "show":
            return command_filters_show(sub_args)
        if sub == "set" and sub_args:
            if sub_args[0].lower() == "salary":
                return command_filters_set_salary(sub_args[1:])
            return CommandResult(
                text=f"Unknown filters set target `{sub_args[0]}`",
                status=400,
            )
        return CommandResult(
            text=f"Unknown filters subcommand `{sub}`",
            status=400,
        )

    if cmd == "profiles" and args and args[0].lower() == "list":
        return command_profiles_list()

    if cmd == "sources" and args and args[0].lower() == "list":
        return command_sources_list()
    if cmd == "sources" and args and args[0].lower() == "set":
        return command_sources_set(args[1:])

    if cmd == "schedule" and args:
        sub = args[0].lower()
        sub_args = args[1:]
        if sub == "show":
            # pass through profile/rule flags
            try:
                profile_name = _get_profile_name(sub_args)
                rule_name = _get_rule_name(sub_args, profile_name)
                expr = get_schedule(rule_name)
                if not expr:
                    return CommandResult(
                        text=f"Schedule not set for rule `{rule_name}`."
                    )
                return CommandResult(
                    text=f"Rule `{rule_name}` schedule: `{expr}`"
                )
            except ScheduleError as e:
                return CommandResult(text=str(e), status=400)
        if sub == "set":
            return command_schedule_set(sub_args)
        return CommandResult(
            text=f"Unknown schedule subcommand `{sub}`",
            status=400,
        )

    return CommandResult(
        text=f"Unknown command `{cmd}`. Try `help`.",
        status=400,
    )

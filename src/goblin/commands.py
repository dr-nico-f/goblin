"""
Lightweight command parsing for Slack slash commands or mentions.

Current commands (extendable):
  - help
  - status [--profile PROFILE]
  - run [--profile PROFILE] [--source remotive|stub] [--limit N]
  - filters show [--profile PROFILE]
  - filters salary [--profile PROFILE]                # view salary filter
  - filters set salary <min> [--allow-missing true|false] [--profile PROFILE]
  - ranking show [--profile PROFILE]
  - ranking set <weight> <value> [--profile PROFILE]
  - profiles list
  - sources list
  - schedule show
  - schedule set <expr>   (stub; informational only)
"""

import asyncio
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import List, Optional

import yaml

from goblin.collectors.remotive import fetch_remotive
from goblin.config import load_sources
from goblin.dedup import cache_file, fingerprint, load_seen, save_seen
from goblin.fetch import fetch_stub
from goblin.filter_store import (
    load_profile_filters,
    save_profile_filters,
    load_profile_ranking,
    save_profile_ranking,
)
from goblin.filters import matches
from goblin.profiles import get_profile, load_profiles, get_profile_for_slack
from goblin.rank import load_profile_weights, score as score_job
from goblin.schedule import ScheduleError, get_schedule, set_schedule
from goblin.slack import job_to_blocks, post_blocks


@dataclass
class CommandResult:
    text: str
    blocks: Optional[List[dict]] = None
    status: int = 200


def _get_profile_name(
    args: List[str],
    default: str = "nick",
    user_id: str | None = None,
    channel_id: str | None = None,
) -> str:
    if "--profile" in args:
        idx = args.index("--profile")
        if idx + 1 < len(args):
            return args[idx + 1]
    return get_profile_for_slack(
        user_id=user_id,
        channel_id=channel_id,
        default=default,
    )


def _format_salary_info(filters: dict) -> str:
    salary_cfg = filters.get("salary", {}) or {}
    min_salary = salary_cfg.get("min")
    allow_missing = bool(salary_cfg.get("allow_missing", False))
    if min_salary is None:
        return "*Salary filter*: not set"
    return (
        "*Salary filter*: "
        f"min=${min_salary:,} "
        f"(allow_missing={allow_missing})"
    )


def _display_profile(name: str) -> str:
    return name.title()


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
        "• `ranking show [--profile nick]` — show ranking weights",
        "• `ranking set <weight> <value> [--profile nick]` — update weight",
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


def command_status(
    args: List[str],
    user_id: str | None = None,
    channel_id: str | None = None,
) -> CommandResult:
    profile_name = _get_profile_name(
        args,
        user_id=user_id,
        channel_id=channel_id,
    )
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

    profile_label = _display_profile(profile_name)
    source_label = "Remotive"
    lines = [
        f"*Profile*: {profile_label}",
        f"*Channel*: {prof.get('channel', 'unset')}",
        f"*Default source*: *{source_label}* "
        f"(limit={remotive_cfg.get('limit', 'n/a')}, "
        f"category={remotive_cfg.get('category', 'n/a')}, "
        f"query='{remotive_cfg.get('query', '')}')",
        f"*{_format_salary_info(filters)}*",
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


def command_filters_salary(
    args: List[str],
    user_id: str | None = None,
    channel_id: str | None = None,
) -> CommandResult:
    profile_name = _get_profile_name(
        args,
        user_id=user_id,
        channel_id=channel_id,
    )
    profile_label = _display_profile(profile_name)
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
                "text": f"*Profile*: {profile_label}\n{txt}",
            },
        }
    ]
    return CommandResult(text=txt, blocks=blocks)


def command_filters_show(
    args: List[str],
    user_id: str | None = None,
    channel_id: str | None = None,
) -> CommandResult:
    profile_name = _get_profile_name(
        args,
        user_id=user_id,
        channel_id=channel_id,
    )
    profile_label = _display_profile(profile_name)
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
        f"*Profile*: {profile_label}",
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


def _cron_to_text(expr: str) -> str:
    """
    Friendly-ish description for AWS cron (6 fields) or 5-field cron.
    Handles simple wildcards, single values, ranges, lists, and steps
    for minutes/hours/dow. Not a full cron parser, but good enough for
    common schedules.
    """
    expr = expr.strip()
    if expr.startswith("cron(") and expr.endswith(")"):
        expr = expr[5:-1]
    parts = expr.split()
    if len(parts) not in (5, 6):
        return expr
    # AWS: min hour dom month dow [year]
    # Standard: min hour dom month dow
    minute = parts[0]
    hour = parts[1] if len(parts) >= 2 else "*"
    dom = parts[2] if len(parts) >= 3 else "*"
    month = parts[3] if len(parts) >= 4 else "*"
    dow = parts[4] if len(parts) >= 5 else "*"
    year = parts[5] if len(parts) == 6 else ""

    def fmt_time(hh: str, mm: str) -> str:
        if hh == "*" and mm == "*":
            return "every minute"
        if hh == "*" and "/" in mm:
            return f"every {mm.split('/')[1]} minutes"
        if hh == "*":
            return f"every hour at :{mm.zfill(2)}"
        if "/" in hh:
            step = hh.split("/")[1]
            return f"every {step} hours at :{mm.zfill(2)} ET"
        # convert to ET for readability
        hh_int = int(hh)
        mm_int = int(mm)
        utc_dt = datetime.now(timezone.utc).replace(
            hour=hh_int, minute=mm_int, second=0, microsecond=0
        )
        et_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))
        et_str = et_dt.strftime("%-I:%M %p ET")
        return et_str

    def fmt_field(val: str, label: str, names: dict | None = None) -> str:
        if val in ("*", "?"):
            return f"every {label}"
        if "/" in val:
            base, step = val.split("/", 1)
            base_txt = "all" if base == "*" else base
            return f"{label} every {step} from {base_txt}"
        if "-" in val:
            a, b = val.split("-", 1)
            a = names.get(a, a) if names else a
            b = names.get(b, b) if names else b
            return f"{label} {a}–{b}"
        if "," in val:
            items = [names.get(x, x) if names else x for x in val.split(",")]
            return f"{label} {', '.join(items)}"
        return f"{label} {names.get(val, val) if names else val}"

    dow_names = {
        "0": "Sun",
        "1": "Mon",
        "2": "Tue",
        "3": "Wed",
        "4": "Thu",
        "5": "Fri",
        "6": "Sat",
        "7": "Sun",
        "SUN": "Sun",
        "MON": "Mon",
        "TUE": "Tue",
        "WED": "Wed",
        "THU": "Thu",
        "FRI": "Fri",
        "SAT": "Sat",
    }
    month_names = {
        "1": "Jan",
        "2": "Feb",
        "3": "Mar",
        "4": "Apr",
        "5": "May",
        "6": "Jun",
        "7": "Jul",
        "8": "Aug",
        "9": "Sep",
        "10": "Oct",
        "11": "Nov",
        "12": "Dec",
        "JAN": "Jan",
        "FEB": "Feb",
        "MAR": "Mar",
        "APR": "Apr",
        "MAY": "May",
        "JUN": "Jun",
        "JUL": "Jul",
        "AUG": "Aug",
        "SEP": "Sep",
        "OCT": "Oct",
        "NOV": "Nov",
        "DEC": "Dec",
    }

    time_txt = fmt_time(hour, minute)
    dom_txt = fmt_field(dom, "day of month")
    dow_txt = fmt_field(dow, "weekday(s)", dow_names)
    month_txt = fmt_field(month, "month(s)", month_names)
    year_txt = "" if not year or year == "*" else f"in year {year}"

    cadence_parts: list[str] = []
    if dom in ("*", "?") and dow in ("*", "?"):
        cadence_parts.append("every day")
    elif dow not in ("*", "?"):
        cadence_parts.append(dow_txt)
    elif dom not in ("*", "?"):
        cadence_parts.append(dom_txt)
    if month != "*":
        cadence_parts.append(month_txt)
    if year_txt:
        cadence_parts.append(year_txt)

    cadence = ", ".join(cadence_parts) if cadence_parts else ""
    if cadence:
        return f"{time_txt}, {cadence}"
    return time_txt


def command_filters_set_salary(
    args: List[str],
    user_id: str | None = None,
    channel_id: str | None = None,
) -> CommandResult:
    profile_name = _get_profile_name(
        args,
        user_id=user_id,
        channel_id=channel_id,
    )
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

    profile_label = _display_profile(profile_name)
    txt = _format_salary_info(data)
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Profile*: {profile_label}\n{txt}",
            },
        }
    ]
    return CommandResult(text=txt, blocks=blocks)


def command_ranking_show(
    args: List[str],
    user_id: str | None = None,
    channel_id: str | None = None,
) -> CommandResult:
    profile_name = _get_profile_name(
        args,
        user_id=user_id,
        channel_id=channel_id,
    )
    profile_label = _display_profile(profile_name)
    prof = get_profile(profile_name)
    if not prof:
        return CommandResult(
            text=f"Unknown profile `{profile_name}`",
            status=400,
        )
    rank_path = prof.get("ranking", "configs/ranking.yaml")
    weights = load_profile_weights(profile_name, rank_path)
    lines = [f"*Profile*: {profile_label}", "*Ranking weights*:"]
    for k, v in sorted(weights.items()):
        lines.append(f"- {k}: {v}")
    txt = "\n".join(lines)
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": txt}}]
    return CommandResult(text=txt, blocks=blocks)


def command_ranking_set(
    args: List[str],
    user_id: str | None = None,
    channel_id: str | None = None,
) -> CommandResult:
    if len(args) < 2:
        return CommandResult(
            text="Usage: ranking set <weight> <value> [--profile nick]",
            status=400,
        )
    weight_key = args[0]
    try:
        weight_val = float(args[1])
    except ValueError:
        return CommandResult(
            text="Value must be a number",
            status=400,
        )
    profile_name = _get_profile_name(
        args,
        user_id=user_id,
        channel_id=channel_id,
    )
    profile_label = _display_profile(profile_name)
    prof = get_profile(profile_name)
    if not prof:
        return CommandResult(
            text=f"Unknown profile `{profile_name}`",
            status=400,
        )
    rank_path = prof.get("ranking", "configs/ranking.yaml")
    data = load_profile_ranking(profile_name, rank_path)
    weights = data.get("weights") or {}
    weights[weight_key] = weight_val
    data["weights"] = weights
    save_profile_ranking(profile_name, data, rank_path)

    lines = [f"*Profile*: {profile_label}", "*Ranking weights*:"]
    for k, v in sorted(weights.items()):
        lines.append(f"- {k}: {v}")
    txt = "\n".join(lines)
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": txt}}]
    return CommandResult(text=txt, blocks=blocks)


def command_profiles_list() -> CommandResult:
    profiles = (load_profiles().get("profiles") or {}).keys()
    if not profiles:
        return CommandResult(text="No profiles found")
    names = [p.title() for p in sorted(profiles)]
    txt = "Profiles:\n• " + "\n• ".join(names)
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Profiles"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": txt}},
    ]
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
    txt = "Sources:\n• " + "\n• ".join(parts)
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Sources"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": txt}},
    ]
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
        friendly = _cron_to_text(expr)
        txt = (
            f"*Schedule:* Runs {friendly}\n"
            f"*Rule name:* `{rule_name}`\n"
            f"*Cron expression:* `{expr}`"
        )
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
        profile_name = _get_profile_name(rest, user_id=None, channel_id=None)
        rule_name = _get_rule_name(rest, profile_name)
        new_expr = set_schedule(expr, rule_name)
        txt = f"Rule `{rule_name}` updated to `{new_expr}`"
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": txt}}]
        return CommandResult(text=txt, blocks=blocks)
    except ScheduleError as e:
        return CommandResult(text=str(e), status=400)


def command_run(
    args: List[str],
    user_id: str | None = None,
    channel_id: str | None = None,
) -> CommandResult:
    profile_name = _get_profile_name(
        args,
        user_id=user_id,
        channel_id=channel_id,
    )
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
    weights = load_profile_weights(profile_name, rank_path)
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
        profile_label = _display_profile(profile_name)
        lines = [f"[{profile_label}] Preview (no post)."]
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
                "text": (
                    "Goblin: "
                    f"{source} matches "
                    f"({_display_profile(profile_name)})"
                ),
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
            f"[{_display_profile(profile_name)}] "
            f"Posted {len(new)} new job(s). "
            f"fetched={len(jobs)} matched={len(matched)} "
            f"new={len(new)}"
        ),
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"[{_display_profile(profile_name)}] "
                        f"Posted {len(new)} new job(s).\n"
                        f"fetched={len(jobs)} matched={len(matched)} "
                        f"new={len(new)}"
                    ),
                },
            }
        ],
    )


def handle_command(
    text: str,
    user_id: str | None = None,
    channel_id: str | None = None,
) -> CommandResult:
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
        return command_status(args, user_id=user_id, channel_id=channel_id)

    if cmd == "run":
        return command_run(args, user_id=user_id, channel_id=channel_id)

    if cmd == "filters" and args:
        sub = args[0].lower()
        sub_args = args[1:]
        if sub == "salary":
            return command_filters_salary(
                sub_args,
                user_id=user_id,
                channel_id=channel_id,
            )
        if sub == "show":
            return command_filters_show(
                sub_args,
                user_id=user_id,
                channel_id=channel_id,
            )
        if sub == "set" and sub_args:
            if sub_args[0].lower() == "salary":
                return command_filters_set_salary(
                    sub_args[1:],
                    user_id=user_id,
                    channel_id=channel_id,
                )
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

    if cmd == "ranking" and args:
        sub = args[0].lower()
        sub_args = args[1:]
        if sub == "show":
            return command_ranking_show(
                sub_args,
                user_id=user_id,
                channel_id=channel_id,
            )
        if sub == "set":
            return command_ranking_set(
                sub_args,
                user_id=user_id,
                channel_id=channel_id,
            )
        return CommandResult(
            text=f"Unknown ranking subcommand `{sub}`",
            status=400,
        )

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
                profile_name = _get_profile_name(
                    sub_args,
                    user_id=user_id,
                    channel_id=channel_id,
                )
                rule_name = _get_rule_name(sub_args, profile_name)
                expr = get_schedule(rule_name)
                if not expr:
                    return CommandResult(
                        text=f"Schedule not set for rule `{rule_name}`."
                    )
                friendly = _cron_to_text(expr)
                txt = (
                    f"*Schedule:* Runs {friendly}\n"
                    f"*Rule name:* `{rule_name}`\n"
                    f"*Cron schedule:* `{expr}`"
                )
                blocks = [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": txt},
                    }
                ]
                return CommandResult(text=txt, blocks=blocks)
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

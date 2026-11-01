"""Autonomous quality and safety gate.

There is no human approval step, so this gate is intentionally
conservative. Doubt means rejection; legitimate dual-use security
projects can pass only with an explicit flag that the formatter turns
into a warning.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

BLOCK_PATTERNS = [
    r"\bstealer\b",
    r"\bkeylogger\b",
    r"\btoken grabber\b",
    r"\bcookie stealer\b",
    r"\bcredential harvesting\b",
    r"\bphishing (?:kit|page|tool)\b",
    r"\bwallet drainer\b",
    r"\bcrypto drainer\b",
    r"\bpassword cracker\b",
    r"\baccount cracker\b",
    r"\bkeygen\b",
    r"\bsms bomber\b",
    r"\bddos (?:tool|script|attack)\b",
    r"\bremote access trojan\b",
    r"\baimbot\b",
    r"\bgame cheat\b",
    r"\bbypass paywall\b",
    r"\bspam bot\b",
    r"\bcarding\b",
    r"\bchecker combo\b",
    r"\bfake (?:followers|likes)\b",
    r"\bransomware\b",
    r"\bbotnet\b",
]
_BLOCK_RE = re.compile("|".join(f"(?:{p})" for p in BLOCK_PATTERNS), re.I)

_DUAL_USE_TERMS = {
    "security",
    "penetration-testing",
    "pentest",
    "vulnerability",
    "vulnerability-scanner",
    "exploit",
    "osint",
    "network-scanner",
    "password-audit",
    "red-team",
    "ctf",
}


@dataclass(frozen=True)
class GateConfig:
    min_stars: int = 100
    gem_min_stars: int = 30
    gem_min_stars_per_day: float = 2.0
    max_staleness_days: int = 180
    min_readme_chars: int = 500
    min_contributors: int = 2
    min_forks: int = 5


@dataclass
class GateDecision:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    is_hidden_gem: bool = False
    is_dual_use: bool = False


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def license_spdx(project: dict[str, Any]) -> str:
    lic = project.get("license")
    if isinstance(lic, dict):
        spdx = str(lic.get("spdx_id") or "").strip()
        if spdx.upper() in {"NOASSERTION", "NONE"}:
            return ""
        return spdx
    text = str(lic or "").strip()
    return "" if text.upper() in {"NOASSERTION", "NONE"} else text


def _int(project: dict[str, Any], *keys: str) -> int:
    for key in keys:
        try:
            if project.get(key) is not None:
                return int(project[key])
        except (TypeError, ValueError):
            continue
    return 0


def is_dual_use(project: dict[str, Any]) -> bool:
    topics = {str(t).lower() for t in project.get("topics") or []}
    if topics & _DUAL_USE_TERMS:
        return True
    safety = str(project.get("safety") or "").lower()
    if safety == "dual_use":
        return True
    haystack = f"{project.get('name') or ''} {project.get('description') or ''}".lower()
    return any(term.replace("-", " ") in haystack for term in ("penetration testing", "vulnerability scanner", "red team"))


def evaluate(project: dict[str, Any], cfg: GateConfig = GateConfig()) -> GateDecision:
    reasons: list[str] = []
    now = datetime.now(timezone.utc)

    safety = str(project.get("safety") or "ok").lower()
    if safety not in {"ok", "dual_use"}:
        reasons.append(f"safety:{safety}")

    haystack = " ".join(
        [
            str(project.get("name") or ""),
            str(project.get("full_name") or ""),
            str(project.get("description") or ""),
            str(project.get("primary_use_case") or ""),
        ]
        + [str(t) for t in project.get("topics") or []]
    )
    blocked = _BLOCK_RE.search(haystack)
    if blocked:
        reasons.append(f"blocklist:{blocked.group(0).lower()}")

    if project.get("archived"):
        reasons.append("archived")
    if project.get("fork"):
        reasons.append("fork")
    if project.get("disabled"):
        reasons.append("disabled")
    if not license_spdx(project):
        reasons.append("no_license")

    created = parse_dt(project.get("created_at"))
    if created is not None and created > now:
        reasons.append("created_in_future")

    pushed = parse_dt(project.get("pushed_at") or project.get("last_commit_date") or project.get("updated_at"))
    if pushed is None:
        reasons.append("no_push_date")
    elif pushed > now:
        reasons.append("pushed_in_future")
    elif (now - pushed).days > cfg.max_staleness_days:
        reasons.append(f"stale>{cfg.max_staleness_days}d")

    contributors = _int(project, "contributors_count")
    forks = _int(project, "forks", "forks_count")
    issues = _int(project, "open_issues", "open_issues_count")
    community = contributors >= cfg.min_contributors or forks >= cfg.min_forks or issues >= 1
    if not community:
        reasons.append("no_community")

    readme = str(project.get("readme") or project.get("readme_excerpt") or "")
    if not project.get("has_readme") and len(readme.strip()) < cfg.min_readme_chars:
        reasons.append("no_readme")

    stars = _int(project, "stars", "stargazers_count")
    is_gem = False
    if stars < cfg.min_stars:
        if created is None or created > now:
            reasons.append(f"stars<{cfg.min_stars}")
        else:
            age_days = max(1, (now - created).days)
            velocity = stars / age_days
            if stars >= cfg.gem_min_stars and velocity >= cfg.gem_min_stars_per_day:
                is_gem = True
            else:
                reasons.append(f"stars<{cfg.min_stars}")

    dual = is_dual_use(project)
    return GateDecision(
        ok=not reasons,
        reasons=reasons,
        is_hidden_gem=is_gem and not reasons,
        is_dual_use=dual,
    )

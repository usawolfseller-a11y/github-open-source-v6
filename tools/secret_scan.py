#!/usr/bin/env python3
"""Small tracked-file secret scanner for CI.

This is a conservative tripwire, not a replacement for GitHub secret
scanning. It looks for credential-shaped strings in the repository while
ignoring documented environment-variable names and empty examples.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

PATTERNS = [
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{30,}\b"),  # Telegram bot token shape
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),  # Google API key shape
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|app[_-]?password)\s*=\s*[A-Za-z0-9_./+=-]{20,}"),
]

ALLOW_SUBSTRINGS = (
    ".env.example",
    "TOKEN=",
    "API_KEY=",
    "PASSWORD=",
)


def tracked_files() -> list[Path]:
    try:
        out = subprocess.check_output(["git", "ls-files"], text=True)
        return [Path(p) for p in out.splitlines() if p]
    except Exception:
        return [p for p in Path(".").rglob("*") if p.is_file() and ".git" not in p.parts]


def main() -> int:
    findings = []
    for path in tracked_files():
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if path.name == ".env.example" and line.strip().endswith("="):
                continue
            for pattern in PATTERNS:
                if pattern.search(line):
                    # Permit prose/code that names an env var without a real value.
                    if line.strip().endswith("=") or "os.getenv" in line or "secrets." in line:
                        continue
                    findings.append(f"{path}:{lineno}: credential-shaped string")
                    break
    if findings:
        print("\n".join(findings))
        return 1
    print("secret-scan: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

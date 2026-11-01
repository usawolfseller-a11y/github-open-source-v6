"""Production card renderer for the adopted v6 design system.

Primary: Editorial Daily. Neon Terminal is used only for CLI/TUI
projects. Glass Aurora is reserved for AI Brief. The Sunday digest uses
an Editorial "Sunday Edition" variant.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .gate import parse_dt

W, H = 1200, 630
BRAND = "@GitHub_Open_Source"
_FONT_DIRS = [
    Path("/usr/share/fonts/truetype/DejaVu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype/freefont"),
]
_FONT_FILES = {
    ("sans", False): ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
    ("sans", True): ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
    ("serif", False): ["DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"],
    ("serif", True): ["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"],
    ("mono", False): ["DejaVuSansMono.ttf", "LiberationMono-Regular.ttf"],
    ("mono", True): ["DejaVuSansMono-Bold.ttf", "LiberationMono-Bold.ttf"],
}


def _font(kind: str = "sans", size: int = 32, bold: bool = False):
    for directory in _FONT_DIRS:
        for filename in _FONT_FILES.get((kind, bold), []):
            path = directory / filename
            if path.exists():
                return ImageFont.truetype(str(path), size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _fit(draw: ImageDraw.ImageDraw, text: str, kind: str, size: int, max_width: int, bold: bool = True, minimum: int = 30):
    current = size
    while current > minimum and draw.textlength(text, font=_font(kind, current, bold)) > max_width:
        current -= 4
    return _font(kind, current, bold)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int = 3) -> list[str]:
    words = str(text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            if len(lines) >= max_lines:
                break
        current = word
    if current and len(lines) < max_lines:
        lines.append(current)
    rendered = " ".join(lines)
    if lines and rendered != " ".join(words):
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    return lines


def _rounded(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _pill(draw, x, y, text, foreground, background, font=None, pad=13, outline=None):
    font = font or _font("sans", 20, True)
    width = int(draw.textlength(text, font=font) + 2 * pad)
    _rounded(draw, (x, y, x + width, y + 38), 19, fill=background, outline=outline, width=2 if outline else 1)
    draw.text((x + pad, y + 8), text, font=font, fill=foreground)
    return width + 10


def _lang_code(language: str) -> str:
    mapping = {
        "Python": "Py",
        "TypeScript": "TS",
        "JavaScript": "JS",
        "Go": "Go",
        "Rust": "Rs",
        "Kotlin": "Kt",
        "Java": "Java",
        "C++": "C++",
        "C#": "C#",
        "Shell": "Sh",
        "Ruby": "Rb",
        "PHP": "PHP",
        "Swift": "Sw",
    }
    return mapping.get(language, (language or "OS")[:2].upper())


def _fmt(value: Any) -> str:
    try:
        number = int(float(value or 0))
    except (TypeError, ValueError):
        return str(value or "0")
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M".replace(".0", "")
    if number >= 10_000:
        return f"{number / 1_000:.1f}k".replace(".0", "")
    return f"{number:,}"


def _freshness(candidate: dict[str, Any]) -> str:
    pushed = parse_dt(candidate.get("pushed_at") or candidate.get("updated_at"))
    if not pushed:
        return "active repository"
    days = max(0, (datetime.now(timezone.utc) - pushed).days)
    if days == 0:
        return "commit today"
    if days == 1:
        return "commit yesterday"
    if days < 30:
        return f"commit {days} days ago"
    if days < 365:
        return f"commit {max(1, days // 30)} months ago"
    return f"commit {days // 365} years ago"


def _license(candidate: dict[str, Any]) -> str:
    lic = candidate.get("license")
    if isinstance(lic, dict):
        return str(lic.get("spdx_id") or lic.get("name") or "—")
    return str(lic or "—")


def _is_terminal(candidate: dict[str, Any], generated: dict[str, Any]) -> bool:
    topics = {str(topic).lower() for topic in candidate.get("topics") or []}
    category = str(generated.get("category") or "").lower()
    return bool(topics & {"cli", "tui", "terminal", "shell", "command-line", "command-line-tool"}) or any(
        token in category for token in ("cli", "tui", "terminal")
    )


def render_editorial_card(
    candidate: dict[str, Any],
    generated: dict[str, Any],
    output_path: Path,
    *,
    issue_number: int | None = None,
) -> Path:
    image = Image.new("RGB", (W, H), (247, 239, 222))
    draw = ImageDraw.Draw(image)
    date_line = datetime.now(timezone.utc).strftime("%A · %B %d, %Y").upper()
    issue = f"No. {issue_number}" if issue_number else "OPEN SOURCE FILE"
    draw.text((600, 36), "THE OPEN SOURCE DAILY", font=_font("serif", 34, True), fill="#1b1710", anchor="ma")
    draw.line((55, 92, 1145, 92), fill="#1b1710", width=4)
    draw.line((55, 103, 1145, 103), fill="#b3342a", width=3)
    draw.text((58, 116), date_line, font=_font("sans", 17, True), fill="#655c4d")
    draw.text((1142, 112), issue, font=_font("serif", 24, True), fill="#b3342a", anchor="ra")
    kicker = "HIDDEN GEM FILE" if candidate.get("is_hidden_gem") else "PROJECT FILE"
    draw.text((58, 145), kicker, font=_font("sans", 17, True), fill="#b3342a")

    name = str(candidate.get("name") or "Open Source Project")
    title_font = _fit(draw, name, "serif", 104, 720, True, 44)
    draw.text((56, 165), name, font=title_font, fill="#17130d")

    hook = str(generated.get("hook") or candidate.get("description") or "")
    hook_lines = _wrap(draw, hook, _font("serif", 38, True), 720, 2)
    y = 292
    for index, line in enumerate(hook_lines):
        color = "#b3342a" if index == len(hook_lines) - 1 and len(hook_lines) > 1 else "#393126"
        draw.text((62, y), line, font=_font("serif", 38, True), fill=color)
        y += 47

    summary = str(generated.get("summary") or candidate.get("description") or "")
    summary_lines = _wrap(draw, summary, _font("sans", 24), 705, 2)
    y = max(y + 8, 405)
    for line in summary_lines:
        draw.text((62, y), line, font=_font("sans", 24), fill="#514940")
        y += 31

    language = str(candidate.get("language") or "Open Source")
    draw.ellipse((885, 165, 1115, 395), outline="#b3342a", width=6)
    code = _lang_code(language)
    code_font = _fit(draw, code, "serif", 84, 170, True, 36)
    draw.text((1000, 218), code, font=code_font, fill="#b3342a", anchor="ma")
    draw.text(
        (1000, 332),
        language.upper(),
        font=_fit(draw, language.upper(), "sans", 19, 170, True, 12),
        fill="#1b1710",
        anchor="ma",
    )

    y = 492
    draw.line((55, y, 1145, y), fill="#1b1710", width=3)
    stats = [
        ("STARS", _fmt(candidate.get("stars") or candidate.get("stargazers_count"))),
        ("FORKS", _fmt(candidate.get("forks") or candidate.get("forks_count"))),
        ("CONTRIB", _fmt(candidate.get("contributors_count"))),
        ("LICENSE", _license(candidate)),
    ]
    for index, (label, value) in enumerate(stats):
        x = 70 + index * 275
        draw.text((x, y + 17), label, font=_font("sans", 17, True), fill="#655c4d")
        draw.text((x, y + 44), str(value), font=_fit(draw, str(value), "serif", 35, 220, True, 20), fill="#1b1710")
    draw.line((55, 585, 1145, 585), fill="#1b1710", width=3)
    draw.text((58, 594), _freshness(candidate), font=_font("sans", 17, True), fill="#514940")
    draw.text((1145, 594), BRAND, font=_font("sans", 19, True), fill="#b3342a", anchor="ra")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def render_terminal_card(
    candidate: dict[str, Any],
    generated: dict[str, Any],
    output_path: Path,
) -> Path:
    image = Image.new("RGB", (W, H), (2, 7, 4))
    draw = ImageDraw.Draw(image)
    for y in range(0, H, 6):
        draw.line((0, y, W, y), fill=(0, 22, 8), width=1)
    _rounded(draw, (35, 30, 1165, 600), 14, outline="#00ff66", width=3)
    draw.rectangle((35, 30, 1165, 82), fill="#04150a")
    for index, color in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        draw.ellipse((58 + index * 34, 47, 78 + index * 34, 67), fill=color)
    draw.text((175, 45), "~/open-source — zsh", font=_font("mono", 21), fill="#8dffb0")

    name = str(candidate.get("name") or "project")
    quick = str(generated.get("quick_start") or "").splitlines()[0] if generated.get("quick_start") else ""
    command = quick if quick and len(quick) <= 64 else f"$ {name.lower()}"
    if not command.startswith("$"):
        command = "$ " + command
    draw.text((65, 108), command, font=_fit(draw, command, "mono", 32, 760, True, 20), fill="#00ff66")
    title = "> " + name.upper()
    draw.text((62, 160), title, font=_fit(draw, title, "mono", 88, 760, True, 38), fill="#eaffef")

    hook = "// " + str(generated.get("hook") or candidate.get("description") or "")
    y = 278
    for line in _wrap(draw, hook, _font("mono", 27), 760, 3):
        draw.text((66, y), line, font=_font("mono", 27), fill="#76f79a")
        y += 36

    rows = [
        ("license", _license(candidate)),
        ("language", candidate.get("language") or "—"),
        ("stars", _fmt(candidate.get("stars") or candidate.get("stargazers_count"))),
        ("forks", _fmt(candidate.get("forks") or candidate.get("forks_count"))),
        ("status", _freshness(candidate)),
    ]
    y = 390
    for key, value in rows:
        draw.text((66, y), f"{key:<12}", font=_font("mono", 24), fill="#59d977")
        draw.text((315, y), str(value), font=_font("mono", 24, True), fill="white")
        y += 32

    _rounded(draw, (875, 170, 1115, 410), 18, outline="#00ff66", width=3)
    draw.text((995, 225), ">_", font=_font("mono", 96, True), fill="#00ff66", anchor="ma")
    draw.text((995, 345), "TERMINAL", font=_font("mono", 20, True), fill="#8dffb0", anchor="ma")
    draw.rectangle((65, 552, 86, 580), fill="#00ff66")
    draw.text((100, 553), BRAND, font=_font("mono", 20), fill="#8dffb0")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def _gradient(first: tuple[int, int, int], second: tuple[int, int, int]) -> Image.Image:
    base = Image.new("RGB", (W, H), first)
    top = Image.new("RGB", (W, H), second)
    mask = Image.linear_gradient("L").resize((W, H)).rotate(90)
    return Image.composite(top, base, mask)


def render_ai_brief_card(
    headline: str,
    standfirst: str,
    official_source: str,
    output_path: Path,
) -> Path:
    image = _gradient((12, 8, 40), (45, 15, 78)).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for x, y, radius, color in [
        (995, 55, 230, (0, 210, 255, 145)),
        (120, 510, 260, (255, 65, 180, 120)),
        (650, 90, 130, (70, 255, 170, 80)),
    ]:
        glow_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(55)))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((80, 55, 1120, 575), radius=34, fill=(10, 16, 42, 122), outline=(255, 255, 255, 130), width=2)
    _pill(od, 115, 88, "AI BRIEF · VERIFIED", "#ffffff", (255, 255, 255, 38), _font("sans", 20, True), outline=(255, 255, 255, 95))
    od.rounded_rectangle((115, 455, 1085, 535), radius=22, fill=(0, 0, 0, 105), outline=(255, 255, 255, 85), width=1)
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)
    draw.text((1085, 88), BRAND, font=_font("mono", 19), fill=(220, 235, 255), anchor="ra")
    y = 145
    for line in _wrap(draw, headline, _font("sans", 57, True), 940, 3):
        draw.text((115, y), line, font=_font("sans", 57, True), fill="white")
        y += 68
    y += 8
    for line in _wrap(draw, standfirst, _font("sans", 29), 920, 3):
        draw.text((117, y), line, font=_font("sans", 29), fill=(225, 232, 255))
        y += 38
    cells = [("OFFICIAL SOURCE", official_source or "Primary source"), ("SPOTTED VIA", "WorldofAI"), ("STATUS", "Confirmed")]
    for index, (key, value) in enumerate(cells):
        x = 145 + index * 320
        draw.text((x, 472), key, font=_font("sans", 15, True), fill=(150, 205, 255))
        draw.text((x, 497), value, font=_fit(draw, value, "sans", 26, 290, True, 17), fill="white")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output_path)
    return output_path


def render_digest_card(records: Iterable[dict[str, Any]], output_path: Path) -> Path:
    image = Image.new("RGB", (W, H), (247, 239, 222))
    draw = ImageDraw.Draw(image)
    draw.text((600, 34), "THE OPEN SOURCE DAILY", font=_font("serif", 30, True), fill="#1b1710", anchor="ma")
    draw.line((55, 82, 1145, 82), fill="#1b1710", width=4)
    draw.line((55, 92, 1145, 92), fill="#b3342a", width=3)
    draw.text((58, 110), "SUNDAY EDITION · WEEK IN REVIEW", font=_font("sans", 18, True), fill="#b3342a")
    draw.text((56, 138), "Top 5 of the Week", font=_font("serif", 72, True), fill="#17130d")
    y = 240
    for index, record in enumerate(list(records)[:5], 1):
        name = str(record.get("name") or record.get("full_name") or "Project")
        meta = " · ".join(part for part in [str(record.get("language") or ""), str(record.get("category") or "")] if part)
        metric = f"score {float(record.get('score') or 0):.0f}"
        draw.text((62, y), str(index), font=_font("serif", 38, True), fill="#b3342a")
        draw.text((115, y), name, font=_fit(draw, name, "sans", 32, 560, True, 19), fill="#17130d")
        draw.text((700, y + 4), meta, font=_font("sans", 21), fill="#655c4d")
        draw.text((1135, y), metric, font=_font("serif", 29, True), fill="#17130d", anchor="ra")
        y += 58
        draw.line((60, y - 10, 1140, y - 10), fill="#d8cdb8", width=2)
    draw.text((58, 562), "Ranked by editorial score until view metrics are connected", font=_font("sans", 19), fill="#655c4d")
    draw.text((1145, 590), BRAND, font=_font("sans", 19, True), fill="#b3342a", anchor="ra")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def render_project_card(
    candidate: dict[str, Any],
    generated: dict[str, Any],
    output_path: Path,
    *,
    issue_number: int | None = None,
) -> tuple[Path, str]:
    if _is_terminal(candidate, generated):
        return render_terminal_card(candidate, generated, output_path), "neon_terminal"
    return render_editorial_card(candidate, generated, output_path, issue_number=issue_number), "editorial_daily"

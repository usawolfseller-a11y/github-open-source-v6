from datetime import datetime, timedelta, timezone

from ghos_v6.formatter import format_project_post, utf16_len, visible_text
from ghos_v6.gate import GateConfig, evaluate
from ghos_v6.rank import rank_candidates, score_candidate


def _project(**overrides):
    now = datetime.now(timezone.utc)
    project = {
        "name": "ExampleTool",
        "full_name": "example/tool",
        "description": "A useful developer tool",
        "url": "https://github.com/example/tool",
        "language": "Python",
        "stars": 1500,
        "forks": 120,
        "open_issues": 4,
        "contributors_count": 8,
        "topics": ["cli", "developer-tools"],
        "license": {"spdx_id": "MIT"},
        "created_at": (now - timedelta(days=400)).isoformat(),
        "pushed_at": (now - timedelta(days=2)).isoformat(),
        "has_readme": True,
        "readme": "x" * 1200,
    }
    project.update(overrides)
    return project


def test_gate_accepts_healthy_project():
    decision = evaluate(_project(), GateConfig())
    assert decision.ok
    assert not decision.is_hidden_gem


def test_gate_rejects_noassertion_license():
    decision = evaluate(_project(license={"spdx_id": "NOASSERTION"}), GateConfig())
    assert not decision.ok
    assert "no_license" in decision.reasons


def test_future_created_repo_cannot_become_hidden_gem():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    decision = evaluate(_project(stars=50, created_at=future), GateConfig())
    assert not decision.ok
    assert "created_in_future" in decision.reasons
    assert not decision.is_hidden_gem


def test_gate_blocks_clearly_malicious_topic():
    decision = evaluate(_project(description="A telegram token grabber"), GateConfig())
    assert not decision.ok
    assert any(reason.startswith("blocklist:") for reason in decision.reasons)


def test_legitimate_security_tool_is_flagged_not_blocked_by_name_only():
    decision = evaluate(
        _project(description="Vulnerability scanner for authorized audits", topics=["security"]),
        GateConfig(),
    )
    assert decision.ok
    assert decision.is_dual_use


def test_formatter_escapes_and_fits():
    project = _project(
        name="<Tool&Co>",
        hook="A <fast> tool",
        readme_summary="Summary with <script>alert(1)</script>",
        key_features=["Feature <one>"],
        who_for="Developers",
        why_now="Actively maintained",
        verdict="Try it",
        quick_start="pip install example",
        discussion_question="Would you use it?",
        is_dual_use=True,
    )
    rendered = format_project_post(project, telegraph_url="https://telegra.ph/example")
    assert "<script>" not in rendered
    assert "Dual-use security tool" in rendered
    assert "Use only on software you own or are authorized to analyze" in rendered
    assert "──────────────" in rendered
    assert "🐍 <b>Python</b>" in rendered
    assert "<code>example/tool</code>" in rendered
    assert "⚡ <b>Quick start</b>" in rendered
    assert rendered.index("⚡ <b>Quick start</b>") < rendered.index("<blockquote")
    assert any(marker in rendered for marker in ("<b>React</b>", "<b>Forward</b>", "<b>Save</b>"))
    assert "Give the repo" not in rendered
    assert 'href="https://t.me/GitHub_Open_Source"' in rendered
    assert "@GitHub_Open_Source" in rendered
    assert utf16_len(visible_text(rendered)) <= 4000


def test_ranking_is_bounded_and_sorted():
    low = _project(name="Low", stars=120)
    high = _project(name="High", stars=12000)
    assert 0 <= score_candidate(low) <= 100
    ranked = rank_candidates([low, high])
    assert ranked[0]["name"] == "High"


def test_formatter_hashtags_use_category_and_block_evasion_terms():
    project = _project(
        name="BrowserTool",
        hook="A fast browser automation tool",
        readme_summary="Automates pages locally.",
        key_features=["Runs browser tasks"],
        category="DevTools",
        topics=["antidetect", "antidetect-browser", "browser", "playwright"],
    )
    rendered = format_project_post(project)
    assert rendered.startswith("🌐 ")
    assert "#devtools" in rendered
    assert "#browser" in rendered
    assert "#antidetect" not in rendered


def _fresh_repo(**overrides):
    base = {
        "full_name": "acme/tool",
        "name": "tool",
        "description": "A tool for developers",
        "language": "Python",
        "topics": ["cli"],
        "stars": 500,
        "forks": 12,
        "contributors_count": 3,
        "readme": "x" * 800,
        "has_readme": True,
        "license": {"spdx_id": "MIT"},
        "created_at": (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
        "pushed_at": datetime.now(timezone.utc).isoformat(),
        "archived": False,
        "fork": False,
        "disabled": False,
    }
    base.update(overrides)
    return base


def test_gate_rejects_markdown_only_projects_and_velocity_spikes():
    from ghos_v6.gate import GateConfig, evaluate

    content_repo = _fresh_repo(non_software_reason="language:markdown")
    assert not evaluate(content_repo, GateConfig()).ok

    spike = _fresh_repo(
        stars=40_000,
        created_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
    )
    reasons = evaluate(spike, GateConfig()).reasons
    assert any(reason.startswith("velocity_too_high") for reason in reasons)


def test_gate_rejects_non_english_readme():
    from ghos_v6.gate import GateConfig, evaluate

    chinese = _fresh_repo(readme="这是一个用于本地运行大模型的推理引擎。" * 40)
    assert "readme_not_english" in evaluate(chinese, GateConfig()).reasons


def test_search_queries_favour_recent_repositories():
    from ghos_v6.sources import build_search_queries

    queries = [query for query, _sort in build_search_queries()]
    created_bounded = [query for query in queries if "created:>=" in query]
    assert len(created_bounded) >= 6
    assert any("pushed:>=" in query for query in queries)  # evergreen lane kept


# --- editorial card: icons, colour and edge cases -------------------------

def test_icon_tables_only_reference_baked_artwork():
    from ghos_v6.cards import ICON_DIR, _LANGUAGE_ICONS, _STACK_ICONS, _slug_file

    slugs = set(_LANGUAGE_ICONS.values()) | set(_STACK_ICONS.values())
    missing = [slug for slug in slugs if not _slug_file("brand", slug).exists()]
    assert not missing, f"icons referenced but not shipped: {missing}"
    ui = [name for name in ("star", "fork", "people", "license", "clock") if not (ICON_DIR / f"ui_{name}.png").exists()]
    assert not ui, f"system icons missing: {ui}"


def test_stack_icons_are_in_brand_colour_and_keep_language_first():
    from ghos_v6.cards import stack_entries

    entries = stack_entries({"language": "Python", "topics": ["docker", "postgresql"], "description": ""})
    assert [label for label, *_ in entries] == ["Python", "Docker", "Postgres"]
    assert entries[0][1] == "python"
    assert all(colour is not None for *_rest, colour in entries)


def test_stack_row_never_overflows_for_long_labels():
    """Four long tool names must still fit; the row degrades to icons only."""
    from PIL import Image, ImageDraw

    from ghos_v6.cards import _draw_stack_row

    image = Image.new("RGB", (1200, 630), "white")
    draw = ImageDraw.Draw(image)
    candidate = {
        "language": "TypeScript",
        "topics": ["kubernetes", "postgresql", "tailwindcss"],
        "description": "nextjs",
    }
    _draw_stack_row(image, draw, candidate, right_limit=1140)
    ink = image.convert("L").point(lambda v: 0 if v > 245 else 255)
    assert ink.getbbox() is not None
    assert ink.getbbox()[2] <= 1140


def test_long_project_name_stays_left_of_the_hero_mark():
    from pathlib import Path

    from PIL import Image

    from ghos_v6.cards import HERO_BOX, render_editorial_card

    out = Path("/tmp/_longname.png")
    render_editorial_card(
        {
            "name": "supercalifragilistic-expialidocious-service",
            "language": "TypeScript",
            "stars": 10,
            "forks": 1,
            "contributors_count": 2,
            "topics": [],
            "license": {"spdx_id": "MIT"},
            "pushed_at": "2026-10-31T00:00:00Z",
        },
        {"card_hook": "Hook", "card_subline": "Sub"},
        out,
    )
    image = Image.open(out).convert("L")
    band = image.crop((0, 165, HERO_BOX[0], 300)).point(lambda v: 0 if v > 200 else 255)
    assert band.getbbox() is not None, "title band is empty"
    assert band.getbbox()[2] < HERO_BOX[0], "title crosses into the hero mark"


def test_missing_values_degrade_to_a_dash_not_a_fake_zero():
    from ghos_v6.cards import _glyph_safe, _font

    font = _font("sans", 20, True)
    assert _glyph_safe("—", font) == "—"  # DejaVu has the em dash
    assert _glyph_safe("\U0001f527", font) == "-"  # emoji would be tofu


def test_photo_caption_fits_telegrams_1024_ceiling():
    """Telegram rejects a caption longer than 1024 chars — the old flow fell
    back to a link preview, which is displayed even smaller than the card."""
    from ghos_v6.formatter import CAPTION_LIMIT, format_project_caption, utf16_len, visible_text

    project = {
        "name": "dbx",
        "full_name": "t8y2/dbx",
        "stars": 28443,
        "forks": 2598,
        "language": "Rust",
        "license": {"spdx_id": "Apache-2.0"},
        "pushed_at": "2026-10-31T00:00:00Z",
        "hook": "Manage over 100 different database types " * 4,
        "key_features": ["Connect to over 100 databases " * 3] * 6,
        "discussion_question": "Which database do you query most?",
    }
    caption = format_project_caption(project)
    assert CAPTION_LIMIT == 1024
    assert utf16_len(visible_text(caption)) <= CAPTION_LIMIT
    assert "@GitHub_Open_Source" in caption

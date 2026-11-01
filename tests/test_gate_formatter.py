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
    assert utf16_len(visible_text(rendered)) <= 4000


def test_ranking_is_bounded_and_sorted():
    low = _project(name="Low", stars=120)
    high = _project(name="High", stars=12000)
    assert 0 <= score_candidate(low) <= 100
    ranked = rank_candidates([low, high])
    assert ranked[0]["name"] == "High"

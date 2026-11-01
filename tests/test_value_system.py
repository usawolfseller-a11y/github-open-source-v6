"""Anti-duplication, polls, measurement and learning."""
from datetime import datetime, timedelta, timezone

from ghos_v6 import dedup, insights, links, polls
from ghos_v6.rank import select_candidate, value_multiplier


# --- anti-duplication -----------------------------------------------------

BUILD = "A fast static site generator written in Rust for docs"


def test_same_repo_inside_cooldown_is_a_duplicate():
    data = {"published": {"acme/site": {"published_at": "2026-10-01T00:00:00Z", "stars": 100, "description": BUILD}}}
    verdict = dedup.check({"full_name": "acme/site", "stars": 120, "description": BUILD}, data)
    assert verdict["verdict"] == "duplicate"


def test_same_repo_after_cooldown_without_milestone_is_still_a_duplicate():
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    data = {"published": {"acme/site": {"published_at": old, "stars": 100, "description": BUILD}}}
    verdict = dedup.check({"full_name": "acme/site", "stars": 110, "description": BUILD}, data)
    assert verdict["verdict"] == "duplicate"


def test_star_milestone_earns_a_revisit():
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    data = {"published": {"acme/site": {"published_at": old, "stars": 100, "description": BUILD}}}
    verdict = dedup.check({"full_name": "acme/site", "stars": 260, "description": BUILD}, data)
    assert verdict["verdict"] == "revisit"
    assert "stars" in verdict["reason"]


def test_renamed_repost_is_caught_by_description_similarity():
    data = {"published": {"old/name": {"published_at": "2026-10-01T00:00:00Z", "stars": 10, "description": BUILD}}}
    copy = "A blazing fast static site generator written in Rust for creating documentation sites easily"
    assert dedup.check({"full_name": "new/name", "description": copy}, data)["verdict"] == "duplicate"


def test_unrelated_project_is_new():
    data = {"published": {"old/name": {"published_at": "2026-10-01T00:00:00Z", "stars": 10, "description": BUILD}}}
    assert dedup.check({"full_name": "pg/proxy", "description": "Postgres wire proxy with query rewriting"}, data)["verdict"] == "new"


# --- measurement ----------------------------------------------------------

def test_views_parsing_handles_telegram_counters():
    assert insights.parse_views("16") == 16
    assert insights.parse_views("1.2K") == 1200
    assert insights.parse_views("12,4 тыс.") == 12400
    assert insights.parse_views("2.3M") == 2300000
    assert insights.parse_views("") == 0


def test_value_score_rewards_above_median_and_votes():
    baseline = 200.0
    quiet = insights.value_score({"views": 100}, median_views=baseline)
    busy = insights.value_score({"views": 400}, median_views=baseline)
    voted = insights.value_score({"views": 400, "votes_share": 0.4}, median_views=baseline)
    assert quiet < busy < voted


def test_value_score_survives_missing_click_layer():
    # No click_rate key at all: the score must still compute.
    assert insights.value_score({"views": 250}, median_views=200) > 0


def test_young_posts_are_not_punished_for_age():
    from ghos_v6.insights import views_at_reference

    fresh = views_at_reference(17, 1)      # 1 hour old
    aged = views_at_reference(208, 314)    # two weeks old
    assert fresh > aged, "a 1h post with 17 views is a hit, not a flop"


def test_normalisation_is_clamped():
    from ghos_v6.insights import views_at_reference

    assert views_at_reference(1000, 0.01) <= 6000
    assert views_at_reference(10, 100000) >= 3


def test_expected_views_grows_monotonically():
    from ghos_v6.insights import expected_views

    ages = [1, 2, 4, 8, 16, 24, 48, 96, 168, 720]
    values = [expected_views(a) for a in ages]
    assert values == sorted(values)


# --- polls ----------------------------------------------------------------

def test_poll_closing_respects_telegram_ten_day_cap():
    assert polls.MAX_POLL_DAYS == 10
    assert polls.DEFAULT_WEEK_POLL_HOURS <= polls.MAX_POLL_DAYS * 24


def test_winner_ignores_zero_vote_options():
    tally = {"options": [{"text": "A", "votes": 0}, {"text": "B", "votes": 4}, {"text": "C", "votes": 0}]}
    assert polls.winner(tally) == {"text": "B", "votes": 4}


# --- links ----------------------------------------------------------------

def test_tracked_link_is_off_by_default(monkeypatch):
    monkeypatch.delenv("REDIRECT_BASE_URL", raising=False)
    assert links.tracked_url("acme/site") == ""


def test_tracked_link_is_stable_and_resolvable(monkeypatch):
    monkeypatch.setenv("REDIRECT_BASE_URL", "https://go.example.dev")
    first = links.tracked_url("Acme/Site")
    assert first == links.tracked_url("acme/site")  # same code, case-insensitive
    assert first.startswith("https://go.example.dev/r/")
    assert len(first.rsplit("/", 1)[-1]) == 8


def test_metrics_refuse_to_measure_a_private_channel(monkeypatch):
    """Post ids collide between the private test channel and the main one."""
    from ghos_v6.config import Config
    from ghos_v6.pipeline import metrics_command
    from ghos_v6.state import StateStore
    import tempfile

    config = Config(app_env="test", publish_target="test", telegram_main_channel_id="@GitHub_Open_Source")
    with tempfile.TemporaryDirectory() as tmp:
        store = StateStore(tmp)
        store.data["published"] = {
            "a/b": {"full_name": "a/b", "telegram_message_id": 5, "published_at": "2026-11-01T00:00:00Z"}
        }
        result = metrics_command(config, store)
    assert result["updated"] == 0
    assert result["reason"] == "channel_not_public"


# --- learning -------------------------------------------------------------

def test_multiplier_is_clamped_and_neutral_without_model():
    assert value_multiplier({"language": "Rust"}, None) == 1.0
    extreme = {"language_multipliers": {"rust": 5.0}, "topic_multipliers": {"cli": 5.0}}
    assert value_multiplier({"language": "Rust", "topics": ["cli"]}, extreme) <= 1.25


def test_learning_can_reorder_near_equal_candidates():
    queue = [
        {"full_name": "a/php", "score": 50, "language": "PHP"},
        {"full_name": "b/rust", "score": 48, "language": "Rust"},
    ]
    model = {"language_multipliers": {"rust": 1.15, "php": 0.9}, "topic_multipliers": {}}
    assert select_candidate(queue, [])["full_name"] == "a/php"
    assert select_candidate(queue, [], model)["full_name"] == "b/rust"


def test_learn_builds_a_model_from_measured_views():
    import tempfile

    from ghos_v6.pipeline import learn_command
    from ghos_v6.state import StateStore

    with tempfile.TemporaryDirectory() as tmp:
        store = StateStore(tmp)
        rows = [("Rust", 300), ("Rust", 280), ("Rust", 320), ("PHP", 90), ("PHP", 110), ("Go", 200)]
        for index, (language, views) in enumerate(rows):
            store.data["published"][f"o{index}/r{index}"] = {
                "full_name": f"o{index}/r{index}",
                "language": language,
                "views": views,
                "published_at": "2026-10-20T00:00:00Z",
                "topics": ["cli"],
            }
        model = learn_command(object(), store)

    assert model["learned"] is True
    assert model["language_multipliers"]["rust"] > 1.0
    assert 0.85 <= model["language_multipliers"]["php"] <= 1.15
    assert all(0.85 <= value <= 1.15 for value in model["language_multipliers"].values())


def test_learn_refuses_to_guess_from_two_posts():
    import tempfile

    from ghos_v6.pipeline import learn_command
    from ghos_v6.state import StateStore

    with tempfile.TemporaryDirectory() as tmp:
        store = StateStore(tmp)
        store.data["published"] = {
            "a/a": {"full_name": "a/a", "language": "Rust", "views": 100, "published_at": "2026-10-20T00:00:00Z"},
            "b/b": {"full_name": "b/b", "language": "Go", "views": 50, "published_at": "2026-10-20T00:00:00Z"},
        }
        result = learn_command(object(), store)
    assert result["learned"] is False
    assert result["reason"] == "not_enough_samples"


def test_channel_polls_must_be_anonymous():
    """Telegram rejects non-anonymous polls in channels — silent failure otherwise."""
    from ghos_v6.polls import is_channel

    assert is_channel("@GitHub_Open_Source")
    assert is_channel("-1003909350927")
    assert not is_channel(8652931211)

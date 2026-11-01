from ghos_v6.telegram_payload import build_buttons


def test_project_buttons_do_not_use_a_star_cta():
    buttons = build_buttons(
        github_url="https://github.com/example/tool",
        telegraph_url="https://telegra.ph/example-tool",
        homepage_url="https://example.com",
    )
    labels = [button["text"] for row in buttons for button in row]
    assert labels == ["🔗 GitHub", "📖 Full breakdown", "🌐 Homepage"]
    assert not any("⭐" in label for label in labels)

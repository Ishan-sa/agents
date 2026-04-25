from pathlib import Path

from outreach_agent.voice import (
    build_system_prompt,
    load_voice_examples,
)


def test_load_voice_examples_reads_file(tmp_path):
    f = tmp_path / "voice.md"
    f.write_text("# voice\n\n## Example 1\n\nhey there\n")
    text = load_voice_examples(f)
    assert "hey there" in text


def test_build_system_prompt_includes_identity_and_examples(tmp_path):
    f = tmp_path / "voice.md"
    f.write_text("EXAMPLE_BODY_TEXT_HERE")
    prompt = build_system_prompt(
        voice_examples_path=f,
        sender_name="Ishan",
        sender_agency_name="TestCo",
        sender_calendar_url="https://cal.com/ishan",
    )
    assert "EXAMPLE_BODY_TEXT_HERE" in prompt
    assert "Ishan" in prompt
    assert "TestCo" in prompt
    assert "https://cal.com/ishan" in prompt
    # Mentions JSON schema and skip rules
    assert '"action"' in prompt
    assert '"draft"' in prompt and '"skip"' in prompt
    assert "subject" in prompt.lower()
    assert "body" in prompt.lower()


def test_build_system_prompt_substitutes_calendar_placeholder(tmp_path):
    """Voice examples reference <CALENDAR_URL> as a placeholder; the prompt
    builder substitutes the actual URL so Claude sees the literal value."""
    f = tmp_path / "voice.md"
    f.write_text("here's my calendar: <CALENDAR_URL>")
    prompt = build_system_prompt(
        voice_examples_path=f,
        sender_name="Ishan",
        sender_agency_name="TestCo",
        sender_calendar_url="https://cal.com/me",
    )
    assert "<CALENDAR_URL>" not in prompt
    assert "https://cal.com/me" in prompt

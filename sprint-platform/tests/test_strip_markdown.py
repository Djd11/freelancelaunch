"""Tests for the strip_markdown template filter (video preview fix).

The Remotion player renders script text word-by-word. Markdown formatting
(**bold**, numbered steps, bullets) must be stripped before reaching the
player so the video preview shows clean, readable text — not raw markup.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _get_strip_markdown():
    """Import the strip_markdown filter from the Flask app."""
    from app import create_app
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    return app.jinja_env.filters["strip_markdown"]


class TestStripMarkdown:
    """strip_markdown must remove all markdown formatting from lesson scripts."""

    def test_bold_markers_removed(self):
        """**bold text** must become 'bold text'."""
        strip = _get_strip_markdown()
        assert strip("This is **important** text") == "This is important text"

    def test_numbered_step_prefix_removed(self):
        """'1. Step text' must become 'Step text'."""
        strip = _get_strip_markdown()
        result = strip("1. Open Klaviyo\n2. Click Flows")
        assert result == "Open Klaviyo\nClick Flows"

    def test_bullet_prefix_removed(self):
        """'- item' must become 'item'."""
        strip = _get_strip_markdown()
        result = strip("- First step\n- Second step")
        assert result == "First step\nSecond step"

    def test_asterisk_bullet_removed(self):
        """'* item' must become 'item'."""
        strip = _get_strip_markdown()
        result = strip("* One\n* Two")
        assert result == "One\nTwo"

    def test_empty_string(self):
        strip = _get_strip_markdown()
        assert strip("") == ""
        assert strip(None) == ""

    def test_no_formatting_unchanged(self):
        """Plain text without markdown must pass through unchanged."""
        strip = _get_strip_markdown()
        plain = "Open the Klaviyo dashboard and navigate to Flows."
        assert strip(plain) == plain

    def test_collapsed_blank_lines(self):
        """Triple+ blank lines must collapse to double."""
        strip = _get_strip_markdown()
        assert strip("A\n\n\n\nB") == "A\n\nB"

    def test_double_escaped_newlines_normalized(self):
        """Literal '\\\\n' must be converted to real newlines before stripping."""
        strip = _get_strip_markdown()
        result = strip("Step 1.\\nStep 2.")
        assert "Step 1." in result
        assert "Step 2." in result

    def test_realistic_llm_script(self):
        """A typical LLM-generated lesson script must be fully de-marked."""
        strip = _get_strip_markdown()
        script = (
            "1. **Log in** to Klaviyo and go to Flows.\n"
            "- Click **Create Flow** and name it \"Welcome Series\".\n"
            "- Add the **Email** block and write your welcome copy.\n"
            "\n"
            "2. **Test** the flow by adding yourself as a subscriber.\n"
            "- Check that the email arrives and links work."
        )
        result = strip(script)
        assert "**" not in result
        assert not result.startswith("1.")
        assert "Log in" in result
        assert "Welcome Series" in result
        assert "Email" in result
        assert "Test" in result

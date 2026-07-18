"""
Step Definitions: Video Script Generation
"""
import json
from behave import given, when, then
from services.video_script_generator import generate_video_content


@given("the LLM API is available")
def step_llm_available(context):
    """Assume LLM is reachable. Will use mock in test if needed."""
    context.llm_available = True


@given("the LLM API is unavailable")
def step_llm_unavailable(context):
    """Simulate LLM being down by setting a bad URL with short timeout."""
    import flask
    with context.app.app_context():
        flask.current_app.config["LLM_API_URL"] = "http://localhost:1/invalid"
        flask.current_app.config["LLM_TIMEOUT"] = 2
    context.llm_available = False


@then("there should be exactly 9 panels")
def step_exactly_9_panels(context):
    """Verify exactly 9 panels were generated."""
    assert len(context.result["panels"]) == 9, f"Expected 9 panels, got {len(context.result['panels'])}"


@given('a topic "{topic}"')
def step_given_topic(context, topic):
    context.test_topic = topic


@given('a day title "{title}"')
def step_given_day_title(context, title):
    context.test_day_title = title


@given('a day description "{desc}"')
def step_given_day_desc(context, desc):
    context.test_desc = desc


@when("the video script generator creates content")
def step_generate_content(context):
    with context.app.app_context():
        context.result = generate_video_content(
            context.test_topic,
            context.test_day_title,
            context.test_desc
        )


@then("the script should be a non-empty string")
def step_script_nonempty(context):
    assert isinstance(context.result["script"], str), "Script should be a string"
    assert len(context.result["script"]) > 50, f"Script too short: {len(context.result['script'])} chars"


@then('the script should contain words about the topic')
def step_script_contains_topic(context):
    words = context.test_topic.lower().split()
    script = context.result["script"].lower()
    assert any(w in script for w in words), f"Script doesn't mention topic words: {words}"


@then("the script should be approximately 250 words long")
def step_script_word_count(context):
    word_count = len(context.result["script"].split())
    assert 100 <= word_count <= 500, f"Script word count {word_count} outside expected range (100-500)"


@then("the panels array should have exactly 9 items")
def step_panels_count(context):
    assert len(context.result["panels"]) == 9, f"Expected 9 panels, got {len(context.result['panels'])}"


@then("each panel should have an id, title, caption, color, and words")
def step_panel_fields(context):
    required = {"id", "title", "caption", "color", "words"}
    for i, panel in enumerate(context.result["panels"]):
        missing = required - set(panel.keys())
        assert not missing, f"Panel {i} missing fields: {missing}"


@then("each panel should have a diagramType and graph configuration")
def step_panel_diagram(context):
    for i, panel in enumerate(context.result["panels"]):
        assert "diagramType" in panel, f"Panel {i} missing diagramType"
        assert "graph" in panel, f"Panel {i} missing graph"
        assert isinstance(panel["graph"], dict), f"Panel {i} graph is not a dict"


@then("the total word count across all panels should match the script word count")
def step_panel_word_count_match(context):
    script_words = len(context.result["script"].split())
    panel_words = sum(len(p["words"].split()) for p in context.result["panels"])
    # Allow some difference due to joining
    assert abs(script_words - panel_words) < 50, \
        f"Script words ({script_words}) vs panel words ({panel_words}) differ by more than 50"


@then('each panel graph should have a valid type (bar, hbar, line, compare, nodes)')
def step_graph_valid_type(context):
    valid_types = {"bar", "hbar", "line", "compare", "nodes"}
    for i, panel in enumerate(context.result["panels"]):
        g = panel["graph"]
        assert g["type"] in valid_types, f"Panel {i} graph type '{g['type']}' not valid"


@then("each graph should have labels, data, and unit fields")
def step_graph_fields(context):
    for i, panel in enumerate(context.result["panels"]):
        g = panel["graph"]
        assert "labels" in g, f"Panel {i} graph missing labels"
        assert "data" in g, f"Panel {i} graph missing data"
        assert "unit" in g or "units" in g, f"Panel {i} graph missing unit"


@then("graph data should be an array of positive numbers")
def step_graph_data_positive(context):
    for i, panel in enumerate(context.result["panels"]):
        data = panel["graph"].get("data", [])
        for j, val in enumerate(data):
            assert isinstance(val, (int, float)) and val >= 0, \
                f"Panel {i} graph data[{j}] = {val} is not a positive number"


@then("content should still be generated using fallback logic")
def step_fallback_content(context):
    assert context.result is not None, "No content was generated"
    assert "script" in context.result, "Fallback result missing script"
    assert "panels" in context.result, "Fallback result missing panels"

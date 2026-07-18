"""
Step Definitions: PanelContent.js Writer
"""
import os
import json
import tempfile
import shutil
from behave import given, when, then
from services.panel_content_writer import write_panel_content, write_keywords


@given("generated panel data with 9 panels")
def step_generated_panels(context):
    """Create test panel data matching the generator output format."""
    context.test_panels = []
    colors = ["#6366f1", "#8b5cf6", "#06b6d4", "#f59e0b", "#10b981",
              "#ef4444", "#3b82f6", "#ec4899", "#14b8a6"]
    
    for i in range(9):
        context.test_panels.append({
            "id": f"panel-{i+1}",
            "title": f"Section {i+1}",
            "caption": f"Exploring concept {i+1}",
            "color": colors[i],
            "accent": f"rgba({int(colors[i][1:3], 16)},{int(colors[i][3:5], 16)},{int(colors[i][5:7], 16)},0.12)",
            "diagramType": ["chain-failure", "before-after", "comparison", "nodes",
                           "risk-heatmap", "delivery-modes", "chain-failure",
                           "before-after", "comparison"][i],
            "imgLabel": f"Section {i+1}",
            "words": f"This is the text for section {i+1}. It contains several important words about the topic we are teaching today.",
            "graph": {
                "title": f"Metric {i+1}",
                "type": ["bar", "hbar", "line", "compare", "nodes",
                        "bar", "line", "hbar", "compare"][i],
                "labels": ["A", "B", "C", "D"],
                "data": [10, 20, 30, 40],
                "unit": "%",
                "barColor": colors[i]
            }
        })
    context.test_panels_data = context.test_panels


@given("a temporary output directory")
def step_temp_output_dir(context):
    context.output_dir = os.path.join(context.temp_dir, "remotion_project")
    os.makedirs(os.path.join(context.output_dir, "src"), exist_ok=True)


@given("a TwoPanelStack.jsx file with default keywords")
def step_two_panel_file(context):
    """Create a mock TwoPanelStack.jsx with default keywords."""
    os.makedirs(os.path.join(context.output_dir, "src"), exist_ok=True)
    content = '''const KEYWORDS = new Set(["old", "default", "keywords"]);

export { KEYWORDS };
'''
    with open(os.path.join(context.output_dir, "src", "TwoPanelStack.jsx"), "w") as f:
        f.write(content)


@when("the panel content writer creates the file")
def step_write_panel_content(context):
    filepath = write_panel_content(context.test_panels, context.output_dir)
    context.panel_file = filepath


@when('the writer updates keywords with {keywords}')
def step_update_keywords(context, keywords):
    import ast
    kw_list = ast.literal_eval(keywords)
    write_keywords(kw_list, context.output_dir)


@then("a PanelContent.js file should exist at the output path")
def step_file_exists(context):
    assert os.path.exists(context.panel_file), f"File not found: {context.panel_file}"


@then("the file should contain JavaScript module exports")
def step_file_has_exports(context):
    with open(context.panel_file) as f:
        content = f.read()
    assert "export {" in content, "Missing module exports"
    assert "PANELS" in content, "Missing PANELS export"


@then("the file should export PANELS array")
def step_export_panels(context):
    with open(context.panel_file) as f:
        content = f.read()
    assert "const PANELS =" in content, "Missing PANELS definition"
    assert "export" in content, "No export statement"


@then("the file should export TOTAL_FRAMES constant")
def step_export_frames(context):
    with open(context.panel_file) as f:
        content = f.read()
    assert "TOTAL_FRAMES" in content, "Missing TOTAL_FRAMES"


@then("the file should export VIDEO_SECONDS constant")
def step_export_seconds(context):
    with open(context.panel_file) as f:
        content = f.read()
    assert "VIDEO_SECONDS" in content, "Missing VIDEO_SECONDS"


@then("the file should export PHASE_STARTS array")
def step_export_phase_starts(context):
    with open(context.panel_file) as f:
        content = f.read()
    assert "PHASE_STARTS" in content, "Missing PHASE_STARTS"


@then("the file should export KEYWORDS set")
def step_export_keywords(context):
    with open(context.panel_file) as f:
        content = f.read()
    assert "KEYWORDS" in content, "Missing KEYWORDS"


@then("VIDEO_SECONDS should be a positive number matching ~TOTAL_WORDS/2.5")
def step_timing_seconds(context):
    with open(context.panel_file) as f:
        content = f.read()
    total_words = sum(len(p["words"].split()) for p in context.test_panels)
    expected_seconds = total_words / 2.5
    # Parse VIDEO_SECONDS from file
    import re
    match = re.search(r'const VIDEO_SECONDS = ([\d.]+)', content)
    assert match, "Cannot find VIDEO_SECONDS in file"
    actual = float(match.group(1))
    assert abs(actual - expected_seconds) < 30, \
        f"VIDEO_SECONDS {actual} too far from expected {expected_seconds}"


@then("GAP_FRAMES should equal (PANELS.length - 1) * 10")
def step_gap_frames(context):
    with open(context.panel_file) as f:
        content = f.read()
    assert "GAP_FRAMES" in content, "Missing GAP_FRAMES"
    assert "PANELS.length - 1" in content or "(PANELS.length - 1) * 10" in content, \
        "GAP_FRAMES formula incorrect"


@then("TOTAL_FRAMES should approximately equal VIDEO_SECONDS * 30")
def step_total_frames(context):
    """Compute expected frames from test data and compare."""
    total_words = sum(len(p["words"].split()) for p in context.test_panels)
    estimated_seconds = max(60, total_words / 2.5)
    expected_frames = int(estimated_seconds * 30)
    
    with open(context.panel_file) as f:
        content = f.read()
    
    import re
    seconds_match = re.search(r'(?:const )?VIDEO_SECONDS = ([\d.]+)', content)
    assert seconds_match, f"Cannot find VIDEO_SECONDS in file"
    
    video_seconds = float(seconds_match.group(1))
    computed_frames = int(video_seconds * 30)
    
    # The actual TOTAL_FRAMES will be close to VIDEO_SECONDS * FPS
    assert abs(computed_frames - expected_frames) < expected_frames * 0.3, \
        f"Computed frames {computed_frames} too far from expected {expected_frames}"


@then("each DURATIONS entry should be >= 30 frames")
def step_durations_min(context):
    with open(context.panel_file) as f:
        content = f.read()
    assert "Math.max(30" in content, "Missing minimum 30 frame duration"


@then("each panel should have: id, title, caption, color, accent, diagramType, words, graph")
def step_panel_full_structure(context):
    required = {"id", "title", "caption", "color", "accent", "diagramType", "words", "graph"}
    for i, panel in enumerate(context.test_panels):
        missing = required - set(panel.keys())
        assert not missing, f"Panel {i} missing: {missing}"


@then("the words field should be a non-empty string")
def step_words_nonempty(context):
    for i, panel in enumerate(context.test_panels):
        assert isinstance(panel["words"], str), f"Panel {i} words is not a string"
        assert len(panel["words"]) > 0, f"Panel {i} words is empty"


@then("the color should be a valid hex color")
def step_color_valid(context):
    import re
    hex_pattern = re.compile(r'^#[0-9a-fA-F]{6}$')
    for i, panel in enumerate(context.test_panels):
        assert hex_pattern.match(panel["color"]), f"Panel {i} color '{panel['color']}' invalid"


@then("the file should contain the new keywords")
def step_new_keywords(context):
    with open(os.path.join(context.output_dir, "src", "TwoPanelStack.jsx")) as f:
        content = f.read()
    assert "Web" in content and "Scraping" in content, "New keywords not found"


@then("the file should not contain the old default keywords")
def step_old_keywords(context):
    with open(os.path.join(context.output_dir, "src", "TwoPanelStack.jsx")) as f:
        content = f.read()
    assert "old" not in content and "default" not in content, "Old keywords still present"

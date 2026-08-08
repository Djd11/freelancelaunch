"""
Video Script & Panel Content Generator — LLM-powered
Generates voiceover script and 9-panel content for any educational topic.
"""
import json
import re


PANEL_COLORS = [
    "#6366f1",  # indigo
    "#8b5cf6",  # purple  
    "#06b6d4",  # cyan
    "#f59e0b",  # amber
    "#10b981",  # emerald
    "#ef4444",  # red
    "#3b82f6",  # blue
    "#ec4899",  # pink
    "#14b8a6",  # teal
]

PANEL_DIAGRAMS = [
    "chain-failure", "before-after", "comparison", "nodes",
    "risk-heatmap", "delivery-modes", "chain-failure", "before-after", "comparison"
]


def generate_video_content(topic: str, day_title: str, description: str) -> dict:
    """
    Generate a voiceover script and 9-panel content for a video.
    Returns: { "script": "...full voiceover...", "panels": [...] }
    """
    prompt = f"""You are an educational video scriptwriter. Create a 2-minute voiceover script about "{topic}" for the lesson: "{day_title}".

Description: {description}

Rules:
1. The script must be ~250 words total, divided into exactly 9 sequential sections.
2. Each section is ~15 seconds of spoken content (25-35 words).
3. The tone is conversational, authoritative, aimed at beginners.
4. Each section flows naturally into the next - it's a continuous voiceover, not disconnected segments.
5. Label each section as [SECTION 1], [SECTION 2], etc.

Output format:

[SECTION 1]
[~30 words of voiceover]

[SECTION 2]
[~30 words of voiceover]

...through [SECTION 9]"""

    # Single source of truth: services/llm_config (big-pickle → deepseek chain)
    from services.llm_config import call_llm
    content = call_llm(prompt, system="You are an educational video scriptwriter. Output clear section-based scripts.", max_tokens=2048)

    if content:
        # Parse sections
        script, panels = _parse_script_to_sections(content, day_title)
        return {"script": script, "panels": panels}

    # Fallback: generate a simple script
    return _fallback_content(topic, day_title)


def _parse_script_to_sections(content: str, day_title: str) -> tuple:
    """Parse LLM output into sections and panel content."""
    # Split by [SECTION N] markers
    sections = re.split(r'\[SECTION\s*\d+\]', content)
    sections = [s.strip() for s in sections if s.strip()]
    
    # Merge if we got a preamble before [SECTION 1]
    if len(sections) > 9:
        sections = sections[-9:]
    # Pad if fewer than 9
    while len(sections) < 9:
        sections.append(sections[-1] if sections else "Continuing our exploration of this topic.")
    
    sections = sections[:9]
    
    # Build the full script
    script = " ".join(sections)
    
    # Generate 9 panels from the sections
    keywords = _extract_keywords(script, day_title)
    
    panels = []
    panel_titles = [
        "The Problem", "Why It Matters", "Core Concept",
        "How It Works", "Key Benefits", "Real-World Example",
        "Common Challenges", "Best Practices", "Your Next Step"
    ]
    
    for i, section_text in enumerate(sections):
        panel = {
            "id": f"panel-{i+1}",
            "title": panel_titles[i],
            "caption": _make_caption(section_text),
            "color": PANEL_COLORS[i],
            "accent": PANEL_COLORS[i].replace("#", "rgba(") + ",0.12)",
            "diagramType": PANEL_DIAGRAMS[i],
            "imgLabel": panel_titles[i][:12],
            "words": section_text,
            "graph": _make_graph(i, section_text, PANEL_COLORS[i]),
        }
        panels.append(panel)
    
    return script, panels


def _make_caption(text: str) -> str:
    """Make a short caption from text."""
    words = text.split()
    if len(words) > 8:
        return " ".join(words[:8]) + "..."
    return text[:60]


def _make_graph(panel_idx: int, text: str, color: str) -> dict:
    """Generate a graph configuration based on the section."""
    graph_types = ["bar", "hbar", "line", "compare", "nodes", "bar", "line", "hbar", "compare"]
    gtype = graph_types[panel_idx]
    
    base = {
        "title": f"Phase {panel_idx + 1}",
        "type": gtype,
        "barColor": color,
    }
    
    if gtype == "bar":
        base["labels"] = ["Low", "Medium", "High", "Optimal"]
        base["data"] = [20 + panel_idx * 8, 40 + panel_idx * 5, 60 + panel_idx * 3, 85 + panel_idx * 2]
        base["unit"] = "%"
    elif gtype == "hbar":
        base["labels"] = ["Step A", "Step B", "Step C", "Step D"]
        base["data"] = [95 - panel_idx * 3, 80 - panel_idx * 2, 65 - panel_idx, 50]
        base["unit"] = ""
    elif gtype == "line":
        base["labels"] = ["Start", "Week 1", "Week 2", "Week 3", "Week 4"]
        base["data"] = [10, 30 + panel_idx * 2, 55 + panel_idx, 75 + panel_idx, 90]
        base["unit"] = "%"
    elif gtype == "compare":
        base["labels"] = ["Before", "After"]
        base["data"] = [80, 95]
        base["unit"] = "%"
    elif gtype == "nodes":
        base["labels"] = ["Input", "Process", "Output"]
        base["data"] = [100, 85, 95]
        base["unit"] = ""
    
    return base


def _extract_keywords(script: str, day_title: str) -> list:
    """Extract technical keywords from the script for highlighting."""
    # Common technical keywords for any topic
    common = [
        "build", "learn", "create", "automate", "develop", "design",
        "system", "workflow", "process", "tool", "skill", "project",
        "client", "freelance", "market", "value", "result"
    ]
    words = script.lower().split()
    found = [w for w in words if len(w) > 5 and w in common or w == w.upper() and len(w) > 2]
    return list(set(found + day_title.lower().split()))[:15]


def _fallback_content(topic: str, day_title: str) -> dict:
    """Generate fallback content when LLM is unavailable."""
    sections = []
    panel_titles = [
        f"Welcome to {topic}",
        f"Why {topic} Matters",
        "Core Concepts",
        "Getting Started",
        "Key Techniques",
        "Real Applications",
        "Common Pitfalls",
        "Pro Tips",
        "Your Action Plan"
    ]
    
    for i in range(9):
        section = f"In this section we explore {panel_titles[i].lower()}. "
        section += f"This is a key part of understanding {topic} and applying it in real freelance projects. "
        section += f"Let's dive deep into the practical aspects. "
        sections.append(section)
    
    script = " ".join(sections)
    panels = []
    
    for i in range(9):
        panels.append({
            "id": f"panel-{i+1}",
            "title": panel_titles[i],
            "caption": f"Exploring {topic} — step {i+1} of 9",
            "color": PANEL_COLORS[i],
            "accent": PANEL_COLORS[i].replace("#", "rgba(") + ",0.12)",
            "diagramType": PANEL_DIAGRAMS[i],
            "imgLabel": panel_titles[i][:12],
            "words": sections[i],
            "graph": _make_graph(i, sections[i], PANEL_COLORS[i]),
        })
    
    return {"script": script, "panels": panels}

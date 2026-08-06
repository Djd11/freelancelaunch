"""
Behave BDD Environment — Hooks and shared context
"""
import os
import sys
import json
import time
import tempfile
import shutil

# Add web-app root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app

AUDIT_DIR = "/tmp/fl_audit_shots"
AUDIT_JSON = "/tmp/fl_audit_behave.json"


def before_all(context):
    """Set up shared test context."""
    context.app = create_app()
    context.app.config["TESTING"] = True
    context.client = context.app.test_client()

    # Temporary directories
    context.temp_dir = tempfile.mkdtemp(prefix="fl_test_")

    # Test data
    context.test_topic = "Web Scraping with Python"
    context.test_day_title = "Introduction to HTTP Requests"
    context.test_desc = "Learn how HTTP requests work for web scraping"

    # Browser setup (Playwright)
    context.browser = None
    context.page = None

    # Audit collection (per-use-case summaries for the HTML report)
    os.makedirs(AUDIT_DIR, exist_ok=True)
    context.audit = []
    context.base_url = None
    context.logged_in = None
    context.console_errors = []


def before_scenario(context, scenario):
    """Set up per-scenario state."""
    context.scenario_data = {}
    context.errors = []
    # context.feature is a behave Feature model (not JSON-serializable) — store
    # just its name so after_all can dump a clean audit JSON.
    feature_obj = getattr(context, "feature", None)
    feature_name = getattr(feature_obj, "name", "") or (feature_obj.filename if feature_obj else "")
    context.scenario_audit = {
        "feature": feature_name,
        "scenario": scenario.name,
        "file": (scenario.filename or "").split("/")[-1],
        "line": scenario.line,
        "status": "passed",
        "started": time.time(),
        "rows": [],
        "screenshots": [],
        "console_errors": [],
    }
    # ensure fresh page per scenario (avoid state bleed)
    if hasattr(context, "page") and context.page:
        try:
            context.page.close()
        except Exception:
            pass
        context.page = None


def after_scenario(context, scenario):
    """Clean up per-scenario state and record the audit entry."""
    if scenario.status == "failed":
        context.scenario_audit["status"] = "failed"
    elif scenario.status == "skipped":
        context.scenario_audit["status"] = "skipped"

    # screenshot of the final state
    if context.page is not None:
        try:
            import re
            safe = re.sub(r"[^A-Za-z0-9_-]+", "_", scenario.name)[:60]
            fp = os.path.join(AUDIT_DIR, f"{safe}_{scenario.line}.png")
            context.page.screenshot(path=fp, full_page=True)
            context.scenario_audit["screenshots"].append(fp)
        except Exception:
            pass

    context.scenario_audit["console_errors"] = list(
        getattr(context, "console_errors", []) or []
    )
    context.scenario_audit["duration"] = round(time.time() - context.scenario_audit["started"], 2)
    context.audit.append(context.scenario_audit)

    if hasattr(context, "page") and context.page:
        try:
            context.page.close()
        except Exception:
            pass
        context.page = None


def after_all(context):
    """Clean up shared resources and dump the audit report."""
    # Browser lives on the object (underscore attr) so it survives scenario pops
    if hasattr(context, "_pw_browser") and context._pw_browser:
        try:
            context._pw_browser.close()
        except Exception:
            pass
    if hasattr(context, "_pw_playwright") and context._pw_playwright:
        try:
            context._pw_playwright.stop()
        except Exception:
            pass
    if hasattr(context, "temp_dir") and os.path.exists(context.temp_dir):
        shutil.rmtree(context.temp_dir, ignore_errors=True)

    # dump audit JSON for the HTML report generator
    try:
        with open(AUDIT_JSON, "w") as f:
            json.dump(context.audit, f, indent=2)
        print(f"\n[AUDIT] {len(context.audit)} scenarios → {AUDIT_JSON}")
    except Exception as e:
        print(f"[AUDIT] failed to dump JSON: {e}")

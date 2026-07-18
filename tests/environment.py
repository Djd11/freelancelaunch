"""
Behave BDD Environment — Hooks and shared context
"""
import os
import sys
import json
import tempfile
import shutil

# Add web-app root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app


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


def before_scenario(context, scenario):
    """Set up per-scenario state."""
    context.scenario_data = {}
    context.errors = []


def after_scenario(context, scenario):
    """Clean up per-scenario state."""
    if hasattr(context, 'page') and context.page:
        context.page.close()
        context.page = None


def after_all(context):
    """Clean up shared resources."""
    if hasattr(context, 'browser') and context.browser:
        context.browser.close()
    if hasattr(context, 'temp_dir') and os.path.exists(context.temp_dir):
        shutil.rmtree(context.temp_dir, ignore_errors=True)

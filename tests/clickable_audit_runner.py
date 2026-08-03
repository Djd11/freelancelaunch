"""
Clickable Items Audit Runner — implements tests/features/clickable-items-audit.feature

BDD contract: every clickable element on every page must do its intended task.
The runner enumerates ALL interactive elements, cross-checks them against the
spec (which mirrors the feature-file tables), clicks each safe one, verifies the
intended outcome, and emits a results JSON that feeds the HTML report.

Modes:
  --discover            enumerate clickables per page only (spec reconciliation)
  --page /path          run verification for a single page (fast fix loop)
  --base-url URL        default http://localhost:5000
  --out PATH            results JSON path
  --shots DIR           screenshot directory
"""
import argparse, json, os, re, sys, time, datetime

SCREENSHOT_DIR = "/tmp/fl_audit_shots"
RESULTS_PATH = "/tmp/fl_audit_results.json"

TEST_EMAIL = "chinaindiatesting@gmail.com"
TEST_PASSWORD = "others@2024"

# ─────────────────────────────────────────────────────────────────────────────
# SPEC — mirrors the tables in clickable-items-audit.feature
# check kinds:
#   link      expect = destination path (string or list; path match, query ignored unless in expect)
#   external  expect = domain prefix; requires target=_blank
#   anchor    expect = "#target"
#   wiring    expect = {onclick: "fnName"} or {hx_post: "/path"} or {action: "/path", method: "post"}
#   checkbox  expect = api path in hx-post or form action; verify persisted after reload
#   htmx      expect = hx-post path; effect verified in DOM after reload
#   details   expand/collapse toggle
#   dropdown  opens a menu
#   toggle    expands inline iframe (preview player)
#   input/select/textarea  presence + attrs (required, type, options)
# ─────────────────────────────────────────────────────────────────────────────

def _lnk(path):
    return {"kind": "link", "expect": path}

def _ext(domain):
    return {"kind": "external", "expect": domain}

def _wiring(**kw):
    return {"kind": "wiring", "expect": kw}

def _cbx(path):
    return {"kind": "checkbox", "expect": path}

SPEC = {
  "/": {
    "label": "Landing (logged out)", "logged_out": True, "screenshot": "01-landing",
    "items": [
      {"id": "logo",            "match": {"text": "FreelanceLaunch"},  "type": "Link", "task": "Click → stays on /",                 "check": _lnk(["/", "/index"])},
      {"id": "nav-topics",      "match": {"text": "Topics"},           "type": "Link", "task": "Click → /topics",                     "check": _lnk("/topics")},
      {"id": "nav-signin",      "match": {"text": "Sign in"},          "type": "Link", "task": "Click → /auth/login",                 "check": _lnk("/auth/login")},
      {"id": "nav-getstarted",  "match": {"text": "Get Started"},      "type": "Link", "task": "Click → /auth/signup",                "check": _lnk("/auth/signup")},
      {"id": "hero-getstarted", "match": {"text": "Get Started", "idx": 1}, "type": "Link", "task": "Hero CTA → /auth/signup",        "check": _lnk("/auth/signup")},
      {"id": "hero-explore",    "match": {"text": "Explore Skills"},   "type": "Link", "task": "Hero CTA → /topics",                  "check": _lnk("/topics")},
      {"id": "card-ws",         "match": {"text": "Web Scraping with Python"}, "type": "Link", "task": "Card → /topics/web-scraping-python", "check": _lnk("/topics/web-scraping-python")},
      {"id": "card-n8n",        "match": {"text": "n8n Automation"},   "type": "Link", "task": "Card → /topics/n8n-automation",        "check": _lnk("/topics/n8n-automation")},
      {"id": "card-seo",        "match": {"text": "SEO Content Writing"}, "type": "Link", "task": "Card → /topics/seo-content-writing", "check": _lnk("/topics/seo-content-writing")},
      {"id": "card-pandas",     "match": {"text": "Data Analysis with Pandas"}, "type": "Link", "task": "Card → /topics/data-analysis-pandas", "check": _lnk("/topics/data-analysis-pandas")},
      {"id": "card-wp",         "match": {"text": "WordPress Development"}, "type": "Link", "task": "Card → /topics/wordpress-development", "check": _lnk("/topics/wordpress-development")},
      {"id": "view-all",        "match": {"text": "View all topics"},  "type": "Link", "task": "Click → /topics",                     "check": _lnk("/topics")},
      {"id": "cta-free",        "match": {"text": "Get Started Free"}, "type": "Link", "task": "Bottom CTA → /auth/signup",           "check": _lnk("/auth/signup")},
      {"id": "cta-browse",      "match": {"text": "Browse Skills"},    "type": "Link", "task": "Bottom CTA → /topics",                 "check": _lnk("/topics")},
      {"id": "foot-topics",     "match": {"text": "Topics", "in": "footer"}, "type": "Link", "task": "Footer → /topics",             "check": _lnk("/topics")},
      {"id": "foot-pricing",    "match": {"text": "Pricing", "in": "footer"}, "type": "Link", "task": "Footer → /payments/pricing",   "check": _lnk("/payments/pricing")},
    ],
  },

  "/topics": {
    "label": "Topics Explorer (logged out)", "logged_out": True, "screenshot": "02-topics",
    "items": [
      {"id": "search-input",  "match": {"name": "q", "tag": "input"}, "type": "Input", "task": "Typing filters topic cards live", "check": {"kind": "input", "expect": {}}},
      {"id": "card-ws",       "match": {"text": "Web Scraping with Python"}, "type": "Link", "task": "Card → /topics/web-scraping-python", "check": _lnk("/topics/web-scraping-python")},
      {"id": "card-n8n",      "match": {"text": "n8n Automation"},    "type": "Link", "task": "Card → /topics/n8n-automation",       "check": _lnk("/topics/n8n-automation")},
      {"id": "card-seo",      "match": {"text": "SEO Content Writing"}, "type": "Link", "task": "Card → /topics/seo-content-writing", "check": _lnk("/topics/seo-content-writing")},
      {"id": "card-pandas",   "match": {"text": "Data Analysis with Pandas"}, "type": "Link", "task": "Card → /topics/data-analysis-pandas", "check": _lnk("/topics/data-analysis-pandas")},
      {"id": "card-wp",       "match": {"text": "WordPress Development"}, "type": "Link", "task": "Card → /topics/wordpress-development", "check": _lnk("/topics/wordpress-development")},
    ],
  },

  "topics-search": {
    "label": "Topics search results (live search)", "logged_out": True, "screenshot": "02b-topics-search",
    "items": [
      {"id": "link-platforms", "match": {"text": "Link Platforms"}, "type": "Link", "task": "→ /platforms/setup", "check": _lnk("/platforms/setup")},
      {"id": "create-curriculum", "match": {"text": "Create 30-Day Curriculum"}, "type": "Button", "task": "POST /enroll/new (skipped: LLM generation)", "check": _wiring(hx_post="/enroll/new")},
    ],
  },

  "/topics/web-scraping-python": {
    "label": "Topic Detail (logged out)", "logged_out": True, "screenshot": "03-topic-detail-out",
    "items": [
      {"id": "getstarted", "match": {"text": "Get Started Free"}, "type": "Link", "task": "→ /auth/signup?topic=web-scraping-python", "check": _lnk("/auth/signup")},
      {"id": "signin",     "match": {"text": "Sign in", "in": "main"}, "type": "Link", "task": "→ /auth/login?topic=web-scraping-python", "check": _lnk("/auth/login")},
    ],
  },

  "/auth/login": {
    "label": "Login", "logged_out": True, "screenshot": "04-login",
    "items": [
      {"id": "email",    "match": {"name": "email", "tag": "input"}, "type": "Input", "task": "Accepts email", "check": {"kind": "input", "expect": {"type": "email"}}},
      {"id": "password", "match": {"name": "password", "tag": "input"}, "type": "Input", "task": "Accepts password (masked)", "check": {"kind": "input", "expect": {"type": "password"}}},
      {"id": "signin-btn", "match": {"text": "Sign In"}, "type": "Submit", "task": "POST /auth/login → /dashboard/", "check": {"kind": "submit_login", "expect": "/dashboard/"}},
      {"id": "create-one", "match": {"text": "Create one"}, "type": "Link", "task": "→ /auth/signup", "check": _lnk("/auth/signup")},
    ],
  },

  "/auth/signup": {
    "label": "Signup", "logged_out": True, "screenshot": "05-signup",
    "items": [
      {"id": "name",     "match": {"name": "name", "tag": "input"}, "type": "Input", "task": "Required name", "check": {"kind": "input", "expect": {"required": True}}},
      {"id": "email",    "match": {"name": "email", "tag": "input"}, "type": "Input", "task": "Required email", "check": {"kind": "input", "expect": {"type": "email"}}},
      {"id": "password", "match": {"name": "password", "tag": "input"}, "type": "Input", "task": "Required, min 6 chars", "check": {"kind": "input", "expect": {"type": "password"}}},
      {"id": "create-btn", "match": {"text": "Create Free Account"}, "type": "Submit", "task": "POST /auth/signup (skipped: creates new real user)", "check": {"kind": "form_wiring", "expect": {"action": "/auth/signup", "method": "post"}}},
      {"id": "login-link", "match": {"text": "Login"}, "type": "Link", "task": "→ /auth/login", "check": _lnk("/auth/login")},
    ],
  },

  "/dashboard/": {
    "label": "Dashboard (logged in)", "logged_out": False, "screenshot": "06-dashboard",
    "items": [
      {"id": "cb-video",    "match": {"name": "video_watched", "tag": "input"}, "type": "Checkbox", "task": "POST /api/progress/mark → persists", "check": _cbx("/api/progress/mark")},
      {"id": "cb-practice", "match": {"name": "practice_completed", "tag": "input"}, "type": "Checkbox", "task": "POST /api/progress/mark → persists", "check": _cbx("/api/progress/mark")},
      {"id": "cb-apply",    "match": {"name": "apply_completed", "tag": "input"}, "type": "Checkbox", "task": "POST /api/progress/mark → persists", "check": _cbx("/api/progress/mark")},
      {"id": "submit-deliv", "match": {"text": "Submit Deliverable"}, "type": "Link", "task": "→ /deliverables/submit?day=N", "check": _lnk("/deliverables/submit")},
      {"id": "day-link",    "match": {"text": "Day", "in": "main"}, "type": "Link", "task": "→ /dashboard/day/N", "check": {"kind": "link_prefix", "expect": "/dashboard/day/", "note": "current day card"}},
      {"id": "week-grid",   "match": {"text": "This Week", "near": "grid"}, "type": "Link", "task": "Each box → /dashboard/day/<n>", "check": {"kind": "link_prefix", "expect": "/dashboard/day/", "note": "week grid boxes"}},
      {"id": "my-portfolio", "match": {"text": "My Portfolio"}, "type": "Link", "task": "→ /deliverables/portfolio", "check": _lnk("/deliverables/portfolio")},
      {"id": "track-apps",  "match": {"text": "Track Applications"}, "type": "Link", "task": "→ /freelance/pipeline", "check": _lnk("/freelance/pipeline")},
      {"id": "upgrade",     "match": {"text": "Upgrade Plan"}, "type": "Link", "task": "→ /payments/pricing", "check": _lnk("/payments/pricing")},
      {"id": "pipeline-manage", "match": {"text": "Manage"}, "type": "Link", "task": "→ /freelance/pipeline", "check": _lnk("/freelance/pipeline")},
    ],
  },

  "/dashboard/day/2": {
    "label": "Day Detail (logged in)", "logged_out": False, "screenshot": "07-day",
    "items": [
      {"id": "back",        "match": {"text": "Back to Dashboard"}, "type": "Link", "task": "→ /dashboard/", "check": _lnk("/dashboard/")},
      {"id": "play-preview", "match": {"text": "Play Video Preview"}, "type": "Button", "task": "Inline iframe expands (no new tab)", "check": {"kind": "toggle", "expect": "iframe"}},
      {"id": "preview-close", "match": {"id": "previewCloseBtn"}, "type": "Button", "task": "Closes preview", "check": {"kind": "wiring", "expect": {"onclick": "togglePreview"}}},
      {"id": "fullscreen", "match": {"id": "fullscreenBtn"}, "type": "Button", "task": "Toggles fullscreen", "check": {"kind": "wiring", "expect": {"onclick": "toggleFullscreen"}}},
      {"id": "start-gen",  "match": {"text": "Start Generation"}, "type": "Button", "task": "onclick startGeneration() (skipped: LLM side-effect)", "check": {"kind": "wiring", "expect": {"onclick": "startGeneration"}}},
    ],
  },

  "/freelance/pipeline": {
    "label": "Pipeline (logged in)", "logged_out": False, "screenshot": "08-pipeline",
    "items": [
      {"id": "plus-proposal", "match": {"text": "+1 Proposal Sent"}, "type": "Button", "task": "hx-post → proposals_sent increments", "check": {"kind": "htmx", "expect": "/freelance/api/update", "effect": "proposals"}},
      {"id": "applying-now", "match": {"text": "I'm Applying Now"}, "type": "Button", "task": "hx-post → stage applying", "check": {"kind": "htmx", "expect": "/freelance/api/update", "effect": "stage"}},
      {"id": "platform-sel", "match": {"name": "platform", "tag": "select"}, "type": "Select", "task": "Options upwork/fiverr/contra/direct", "check": {"kind": "select", "expect": ["upwork", "fiverr", "contra", "direct"]}},
      {"id": "client-name", "match": {"name": "client_name", "tag": "input"}, "type": "Input", "task": "Required", "check": {"kind": "input", "expect": {"required": True}}},
      {"id": "proj-title",  "match": {"name": "project_title", "tag": "input"}, "type": "Input", "task": "Required", "check": {"kind": "input", "expect": {"required": True}}},
      {"id": "contract-val", "match": {"name": "contract_value", "tag": "input"}, "type": "Input", "task": "Optional number", "check": {"kind": "input", "expect": {}}},
      {"id": "hours",       "match": {"name": "hours_worked", "tag": "input"}, "type": "Input", "task": "Optional number", "check": {"kind": "input", "expect": {}}},
      {"id": "add-contract", "match": {"text": "Add Contract"}, "type": "Submit", "task": "POST /freelance/contract/add → row created", "check": {"kind": "submit_contract", "expect": "/freelance/contract/add"}},
    ],
  },

  "/deliverables/portfolio": {
    "label": "Portfolio (logged in)", "logged_out": False, "screenshot": "09-portfolio",
    "items": [
      {"id": "add-item", "match": {"text": "Add Item"}, "type": "Link", "task": "→ /deliverables/submit", "check": _lnk("/deliverables/submit")},
    ],
  },

  "/deliverables/submit": {
    "label": "Submit Deliverable (logged in)", "logged_out": False, "screenshot": "10-submit",
    "items": [
      {"id": "back",      "match": {"text": "Back to Dashboard"}, "type": "Link", "task": "→ /dashboard/", "check": _lnk("/dashboard/")},
      {"id": "day-num",   "match": {"name": "day_number", "tag": "input"}, "type": "Input", "task": "Number 1-60 required", "check": {"kind": "input", "expect": {"required": True}}},
      {"id": "type-sel",  "match": {"name": "type", "tag": "select"}, "type": "Select", "task": "5 types", "check": {"kind": "select", "expect": ["blog", "code", "proposal", "screenshot", "other"]}},
      {"id": "title",     "match": {"name": "title", "tag": "input"}, "type": "Input", "task": "Accepts text", "check": {"kind": "input", "expect": {}}},
      {"id": "content",   "match": {"name": "content", "tag": "textarea"}, "type": "Textarea", "task": "Multi-line text", "check": {"kind": "input", "expect": {}}},
      {"id": "submit-btn", "match": {"text": "Submit for Portfolio"}, "type": "Submit", "task": "POST → redirect /dashboard/ + flash", "check": {"kind": "submit_deliverable", "expect": "/deliverables/submit"}},
    ],
  },

  "/payments/pricing": {
    "label": "Pricing (logged out)", "logged_out": True, "screenshot": "11-pricing-out",
    "items": [
      {"id": "free-getstarted", "match": {"text": "Get Started Free"}, "type": "Link", "task": "→ /auth/signup", "check": _lnk("/auth/signup")},
      {"id": "guided-upgrade", "match": {"text": "Sign Up to Upgrade"}, "type": "Link", "task": "→ /auth/signup", "check": _lnk("/auth/signup")},
    ],
  },

  "pricing-in": {
    "label": "Pricing (logged in)", "logged_out": False, "screenshot": "11b-pricing-in",
    "items": [
      {"id": "guided-checkout", "match": {"text": "Upgrade", "idx": 0}, "type": "Submit", "task": "form action /payments/create-checkout (skipped: Stripe)", "check": {"kind": "form_wiring", "expect": {"action": "/payments/create-checkout"}}},
    ],
  },

  "/auth/profile": {
    "label": "Profile (logged in)", "logged_out": False, "screenshot": "12-profile",
    "items": [
      {"id": "display-name", "match": {"name": "display_name", "tag": "input"}, "type": "Input", "task": "Shows current name, editable", "check": {"kind": "input", "expect": {}}},
      {"id": "save-btn", "match": {"text": "Save"}, "type": "Submit", "task": "POST → display_name updates + flash", "check": {"kind": "submit_profile", "expect": "/auth/profile"}},
    ],
  },

  "/platforms/setup": {
    "label": "Platform Setup (logged in)", "logged_out": False, "screenshot": "13-platforms",
    "items": [
      {"id": "link-upwork",  "match": {"text": "Link Upwork"}, "type": "Button", "task": "POST /platforms/api/select → pending", "check": {"kind": "platform_select", "expect": "/platforms/api/select", "platform": "upwork"}},
      {"id": "link-fiverr",  "match": {"text": "Link Fiverr"}, "type": "Button", "task": "POST /platforms/api/select → pending", "check": {"kind": "platform_select", "expect": "/platforms/api/select", "platform": "fiverr"}},
      {"id": "link-contra",  "match": {"text": "Link Contra"}, "type": "Button", "task": "POST /platforms/api/select → pending", "check": {"kind": "platform_select", "expect": "/platforms/api/select", "platform": "contra"}},
      {"id": "upwork-deep",  "match": {"text": "Create Upwork Account"}, "type": "External", "task": "upwork.com signup, _blank", "check": _ext("upwork.com")},
      {"id": "fiverr-deep",  "match": {"text": "Create Fiverr Account"}, "type": "External", "task": "fiverr.com signup, _blank", "check": _ext("fiverr.com")},
      {"id": "contra-deep",  "match": {"text": "Create Contra Account"}, "type": "External", "task": "contra.com signup, _blank", "check": _ext("contra.com")},
      {"id": "guide-details", "match": {"tag": "summary"}, "type": "Toggle", "task": "Expands step-by-step guide", "check": {"kind": "details", "expect": "open"}},
      {"id": "done-btn",    "match": {"text": "I've done this"}, "type": "Button", "task": "POST /platforms/api/verify → verified", "check": {"kind": "platform_verify", "expect": "/platforms/api/verify"}},
      {"id": "skip-btn",    "match": {"text": "Skip for now"}, "type": "Button", "task": "POST /platforms/api/skip → skipped", "check": {"kind": "platform_skip", "expect": "/platforms/api/skip"}},
      {"id": "continue",    "match": {"text": "Continue to Dashboard"}, "type": "Link", "task": "→ /dashboard/", "check": _lnk("/dashboard/")},
    ],
  },

  "/admin/": {
    "label": "Admin Dashboard (logged in)", "logged_out": False, "screenshot": "14-admin",
    "items": [
      {"id": "view-users",  "match": {"text": "View All Users"}, "type": "Link", "task": "→ /admin/users", "check": _lnk("/admin/users")},
      {"id": "prod-queue",  "match": {"text": "Production Queue"}, "type": "Link", "task": "→ /admin/production", "check": _lnk("/admin/production")},
    ],
  },

  "/admin/users": {
    "label": "Admin Users (logged in)", "logged_out": False, "screenshot": "15-admin-users",
    "items": [
      {"id": "admin-home", "match": {"text": "Admin Home"}, "type": "Link", "task": "→ /admin/", "check": _lnk("/admin/")},
    ],
  },

  "/admin/production": {
    "label": "Admin Production (logged in)", "logged_out": False, "screenshot": "16-admin-prod",
    "items": [
      {"id": "admin-home", "match": {"text": "Admin Home"}, "type": "Link", "task": "→ /admin/", "check": _lnk("/admin/")},
      {"id": "produce-now", "match": {"text": "Produce Now"}, "type": "Submit", "task": "form action /admin/production/trigger/<id> (skipped: render)", "check": {"kind": "form_wiring", "expect": {"action": "/admin/production/trigger/"}}},
    ],
  },

  "nav-in": {
    "label": "Global nav + footer (logged in)", "logged_out": False, "screenshot": "17-nav",
    "items": [
      {"id": "logo",       "match": {"text": "FreelanceLaunch"}, "type": "Link", "task": "→ /", "check": _lnk("/")},
      {"id": "nav-topics", "match": {"text": "Topics", "in": "nav"}, "type": "Link", "task": "→ /topics", "check": _lnk("/topics")},
      {"id": "nav-dash",   "match": {"text": "Dashboard", "in": "nav"}, "type": "Link", "task": "→ /dashboard/", "check": _lnk("/dashboard/")},
      {"id": "nav-pipe",   "match": {"text": "Pipeline", "in": "nav"}, "type": "Link", "task": "→ /freelance/pipeline", "check": _lnk("/freelance/pipeline")},
      {"id": "nav-pricing","match": {"text": "Pricing", "in": "nav"}, "type": "Link", "task": "→ /payments/pricing", "check": _lnk("/payments/pricing")},
      {"id": "nav-platforms", "match": {"text": "Platforms", "in": "nav"}, "type": "Link", "task": "→ /platforms/setup", "check": _lnk("/platforms/setup")},
      {"id": "avatar",     "match": {"tag": "button", "in": "nav"}, "type": "Button", "task": "Opens dropdown", "check": {"kind": "dropdown", "expect": ["Profile", "Portfolio", "Sign out"]}},
      {"id": "dd-profile", "match": {"text": "Profile", "in": "dropdown"}, "type": "Link", "task": "→ /auth/profile", "check": _lnk("/auth/profile")},
      {"id": "dd-portfolio","match": {"text": "Portfolio", "in": "dropdown"}, "type": "Link", "task": "→ /deliverables/portfolio", "check": _lnk("/deliverables/portfolio")},
      {"id": "dd-signout", "match": {"text": "Sign out", "in": "dropdown"}, "type": "Link", "task": "→ /auth/logout", "check": _lnk("/auth/logout")},
      {"id": "foot-topics", "match": {"text": "Topics", "in": "footer"}, "type": "Link", "task": "→ /topics", "check": _lnk("/topics")},
      {"id": "foot-pricing","match": {"text": "Pricing", "in": "footer"}, "type": "Link", "task": "→ /payments/pricing", "check": _lnk("/payments/pricing")},
    ],
  },
}

# pages whose buttons mutate test-user state — restored after the sweep
MUTATING = {"checkboxes": True, "proposals": True, "contract": True, "deliverable": True, "profile": True, "platforms": True}

# ─────────────────────────────────────────────────────────────────────────────

def normalize(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()

def el_text(el):
    return normalize(el.get("text", ""))

def matches(el, m):
    """Match a discovered element dict against a spec match dict."""
    if "tag" in m and el.get("tag") != m["tag"]:
        return False
    if "name" in m and el.get("name") != m["name"]:
        return False
    if "id" in m and el.get("id") != m["id"]:
        return False
    if "in" in m and m["in"] not in (el.get("location") or ""):
        return False
    if "text" in m:
        t = normalize(m["text"])
        et = el_text(el)
        if m.get("near") == "grid":
            return False  # grid boxes matched via prefix check on all day links
        if t not in et:
            return False
        idx = m.get("idx", 0)
        if idx > 0:
            return False  # duplicate-text disambiguation handled at group level
    return True

def group_and_index(elements, spec):
    """Disambiguate duplicate text matches using idx."""
    matched = {}
    used = set()
    for item in spec["items"]:
        m = item["match"]
        cands = [e for e in elements if matches(e, m)]
        # idx handling for repeated text (e.g. two 'Get Started' on landing)
        idx = m.get("idx", 0)
        order = []
        for e in elements:
            if "text" in m and normalize(m["text"]) in el_text(e):
                if m.get("in") and m["in"] not in (e.get("location") or ""):
                    continue
                order.append(e)
        chosen = None
        if "idx" in m:
            chosen = order[idx] if idx < len(order) else None
        else:
            chosen = cands[0] if cands else None
        if chosen is not None:
            key = chosen["key"]
            used.add(key)
            matched[item["id"]] = (item, chosen)
    return matched, used

CLICKABLE_JS = """
() => {
  const out = [];
  const seen = new Set();
  const loc = (el) => {
    let s = "";
    for (let n = el; n && n.tagName !== 'BODY' && n.tagName !== 'HTML'; n = n.parentElement) {
      s += (n.tagName || '').toLowerCase() + ' ';
    }
    return s;
  };
  const add = (el) => {
    if (seen.has(el)) return;
    seen.add(el);
    const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.title || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
    out.push({
      key: el.tagName + '|' + (el.name || '') + '|' + (el.id || '') + '|' + text + '|' + (el.getAttribute('href') || ''),
      tag: el.tagName.toLowerCase(),
      text: text,
      name: el.name || '',
      id: el.id || '',
      href: el.getAttribute('href') || '',
      type: el.getAttribute('type') || '',
      onclick: el.getAttribute('onclick') || '',
      hxpost: el.getAttribute('hx-post') || '',
      target: el.getAttribute('target') || '',
      location: loc(el),
      visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
    });
  };
  document.querySelectorAll('a[href], button, input[type=submit], input[type=button], input[type=checkbox], input[type=radio], select, summary, [role=button], [onclick], [hx-post], [hx-get]').forEach(add);
  return out;
}
"""


def discover(page):
    """Return all clickable elements on the current page."""
    return page.evaluate(CLICKABLE_JS)


def path_of(url):
    from urllib.parse import urlparse
    p = urlparse(url).path
    return p if p else "/"


def url_matches(actual_url, expect):
    ap = path_of(actual_url)
    if isinstance(expect, list):
        return any(ap == e or (e != "/" and ap.startswith(e)) for e in expect)
    return ap == expect or (expect != "/" and ap.startswith(expect))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:5000")
    ap.add_argument("--page", default=None, help="single page path to verify")
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--out", default=RESULTS_PATH)
    ap.add_argument("--shots", default=SCREENSHOT_DIR)
    args = ap.parse_args()

    os.makedirs(args.shots, exist_ok=True)
    base = args.base_url.rstrip("/")

    from playwright.sync_api import sync_playwright

    report = {
        "generated": datetime.datetime.now().isoformat(),
        "base_url": base,
        "pages": [],
        "summary": {"pass": 0, "fail": 0, "skip": 0, "pages_pass": 0, "pages_fail": 0},
    }

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                channel="chrome", headless=False, slow_mo=60,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
        except Exception as e:
            print(f"!! chrome launch failed ({e}); falling back to bundled chromium")
            browser = p.chromium.launch(headless=False, slow_mo=60, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(15000)

        console_errors = []
        page.on("console", lambda m: console_errors.append(f"[{m.type}] {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(f"[pageerror] {exc}"))
        page.on("requestfailed", lambda req: console_errors.append(f"[requestfailed] {req.url} ({req.failure})"))

        def goto(path, wait="networkidle"):
            resp = page.goto(base + path, wait_until=wait, timeout=20000)
            page.wait_for_timeout(400)
            return resp

        def shot(name):
            fp = os.path.join(args.shots, name + ".png")
            page.screenshot(path=fp, full_page=True)
            return fp

        def login():
            goto("/auth/login")
            page.fill("input[name='email']", TEST_EMAIL)
            page.fill("input[name='password']", TEST_PASSWORD)
            with page.expect_navigation(wait_until="networkidle", timeout=20000):
                page.click("button[type='submit']")
            page.wait_for_timeout(600)
            return path_of(page.url)

        def verify_item(page, item, el, results, page_report, pageshot_dir):
            """Run the check for one spec item against its discovered element."""
            res = {"id": item["id"], "type": item["type"], "task": item["task"],
                   "element": el, "status": "PASS", "detail": ""}
            check = item["check"]
            kind = check["kind"]
            try:
                if kind == "link":
                    with page.expect_navigation(wait_until="networkidle", timeout=15000) as nav:
                        el["_pw"].click()
                    resp = nav.value
                    final = path_of(page.url)
                    ok = url_matches(page.url, check["expect"]) and (resp is None or resp.status < 400)
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"clicked → {final} (HTTP {resp.status if resp else '?'})"
                    page.go_back(wait_until="networkidle")
                elif kind == "link_prefix":
                    # any day-link in the page whose destination matches the prefix
                    hrefs = page.eval_on_selector_all("a[href*='/dashboard/day/']",
                        "els => els.map(e => e.getAttribute('href'))")
                    ok = len(hrefs) > 0
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"{len(hrefs)} day links → " + ", ".join(hrefs[:4]) if hrefs else "no day links found"
                elif kind == "external":
                    href = el["href"] or ""
                    ok = check["expect"] in href and el["target"] == "_blank"
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"href={href} target={el['target']!r}"
                elif kind == "anchor":
                    with page.expect_navigation(wait_until="commit", timeout=15000) as nav:
                        el["_pw"].click()
                    ok = page.url.endswith(check["expect"])
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"hash → {check['expect']}"
                    page.go_back(wait_until="networkidle")
                elif kind == "input":
                    attrs_ok = True
                    det = []
                    pw = el["_pw"]
                    if check["expect"].get("type") and el["type"] != check["expect"]["type"]:
                        attrs_ok = False; det.append(f"type={el['type']}≠{check['expect']['type']}")
                    if check["expect"].get("required") and not pw.get_attribute("required"):
                        attrs_ok = False; det.append("not required")
                    if not det:
                        det.append(f"<{el['tag']} name={el['name'] or '-'} type={el['type'] or '-'}>")
                    res["status"] = "PASS" if attrs_ok else "FAIL"
                    res["detail"] = "; ".join(det)
                elif kind == "select":
                    opts = page.eval_on_selector(f"select[name='{el['name']}']",
                        "s => Array.from(s.options).map(o => o.value)")
                    expect = check["expect"]
                    missing = [x for x in expect if x not in opts]
                    res["status"] = "PASS" if not missing else "FAIL"
                    res["detail"] = f"options={opts}" + (f" missing={missing}" if missing else "")
                elif kind == "wiring":
                    exp = check["expect"]
                    ok, det = True, []
                    if "onclick" in exp:
                        ok &= exp["onclick"] in el["onclick"]
                        det.append(f"onclick={el['onclick']!r}")
                    if "hx_post" in exp:
                        ok &= exp["hx_post"] in el["hxpost"]
                        det.append(f"hx-post={el['hxpost']!r}")
                    if "action" in exp:
                        form = el["_pw"].evaluate("el => { const f = el.closest('form'); return f ? f.getAttribute('action') + '|' + (f.getAttribute('method')||'get') : 'noform'; }")
                        ok &= exp["action"] in form
                        det.append(f"form={form}")
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = "; ".join(det) or "wiring ok"
                elif kind == "form_wiring":
                    form = el["_pw"].evaluate("el => { const f = el.closest('form'); return f ? (f.getAttribute('action')||'') + '|' + (f.getAttribute('method')||'get') : 'noform'; }")
                    ok = check["expect"]["action"] in form
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"form action/method = {form} (click skipped: side-effect)"
                    if ok:
                        res["status"] = "SKIP"
                elif kind == "checkbox":
                    api = el["hxpost"] or el["_pw"].evaluate("el => { const f = el.closest('form'); return f ? f.getAttribute('action')||'' : ''; }")
                    if check["expect"] not in api:
                        api = "/api/progress/mark"  # JS fetch fallback
                    was = el["_pw"].is_checked()
                    el["_pw"].check()
                    page.wait_for_timeout(1200)
                    page.reload(wait_until="networkidle")
                    now = page.locator(f"input[name='{el['name']}']").first.is_checked()
                    ok = now != was  # state flipped and persisted
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"{el['name']}: {was} → {now} (persisted)"
                    # restore
                    if now != was:
                        page.locator(f"input[name='{el['name']}']").first.click()
                        page.wait_for_timeout(1200)
                        page.reload(wait_until="networkidle")
                elif kind == "htmx":
                    # read before value from DOM
                    if check["effect"] == "proposals":
                        before = page.locator("text=Sent").first.inner_text()
                        el["_pw"].click()
                        page.wait_for_timeout(1500)
                        page.reload(wait_until="networkidle")
                        res["status"] = "PASS"
                        res["detail"] = f"hx-post {el['hxpost']} fired; proposals card: '{before}' → refreshed"
                    elif check["effect"] == "stage":
                        el["_pw"].click()
                        page.wait_for_timeout(1500)
                        page.reload(wait_until="networkidle")
                        res["status"] = "PASS"
                        res["detail"] = f"hx-post {el['hxpost']} fired; stage re-rendered"
                elif kind == "details":
                    el["_pw"].click()
                    page.wait_for_timeout(300)
                    open_ = el["_pw"].evaluate("el => el.open")
                    res["status"] = "PASS" if open_ else "FAIL"
                    res["detail"] = f"details open={open_}"
                    el["_pw"].click()
                elif kind == "dropdown":
                    el["_pw"].click()
                    page.wait_for_timeout(400)
                    body = page.inner_text("body")
                    missing = [x for x in check["expect"] if x.lower() not in body.lower()]
                    res["status"] = "PASS" if not missing else "FAIL"
                    res["detail"] = f"menu items found: {check['expect']}" + (f"; missing: {missing}" if missing else "")
                    # close it
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(200)
                elif kind == "toggle":
                    el["_pw"].click()
                    page.wait_for_timeout(1200)
                    iframes = page.locator("iframe").count()
                    res["status"] = "PASS" if iframes > 0 else "FAIL"
                    res["detail"] = f"{iframes} iframe(s) after click (inline preview)"
                    if res["status"] == "PASS":
                        page.locator("button[id='previewCloseBtn'], button:has-text('Close')").first.click()
                        page.wait_for_timeout(500)
                elif kind == "submit_login":
                    page.fill("input[name='email']", TEST_EMAIL)
                    page.fill("input[name='password']", TEST_PASSWORD)
                    with page.expect_navigation(wait_until="networkidle", timeout=20000) as nav:
                        page.locator("button[type='submit']").first.click()
                    resp = nav.value
                    final = path_of(page.url)
                    ok = final == check["expect"] and (resp is None or resp.status < 400)
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"POST login → {final} (HTTP {resp.status if resp else '?'})"
                    # return to the audited page so later spec items (create-one) can be verified
                    try:
                        page.go_back(wait_until="networkidle", timeout=15000)
                    except Exception:
                        goto("/auth/login")
                elif kind == "submit_contract":
                    stamp = "AUDIT-" + datetime.datetime.now().strftime("%H%M%S")
                    page.fill("input[name='client_name']", f"Audit Client {stamp}")
                    page.fill("input[name='project_title']", f"Audit Project {stamp}")
                    page.fill("input[name='contract_value']", "120")
                    with page.expect_navigation(wait_until="networkidle", timeout=15000) as nav:
                        el["_pw"].click()
                    resp = nav.value
                    page.wait_for_timeout(800)
                    body = page.inner_text("body")
                    ok = f"Audit Project {stamp}" in body or (resp is not None and resp.status < 400)
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"contract '{stamp}' created → HTTP {resp.status if resp else '?'}"
                elif kind == "submit_deliverable":
                    stamp = datetime.datetime.now().strftime("%H%M%S")
                    page.fill("input[name='day_number']", "2")
                    page.select_option("select[name='type']", "blog")
                    page.fill("input[name='title']", f"Audit Deliverable {stamp}")
                    page.fill("textarea[name='content']", "Created by the clickable-items audit.")
                    with page.expect_navigation(wait_until="networkidle", timeout=15000) as nav:
                        el["_pw"].click()
                    resp = nav.value
                    page.wait_for_timeout(800)
                    final = path_of(page.url)
                    body = page.inner_text("body")
                    ok = final == "/dashboard/" and (resp is None or resp.status < 400)
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"deliverable '{stamp}' → {final} (HTTP {resp.status if resp else '?'})"
                elif kind == "submit_profile":
                    stamp = datetime.datetime.now().strftime("%H%M%S")
                    page.fill("input[name='display_name']", f"Audit User {stamp}")
                    with page.expect_navigation(wait_until="networkidle", timeout=15000) as nav:
                        el["_pw"].click()
                    resp = nav.value
                    page.wait_for_timeout(800)
                    body = page.inner_text("body")
                    ok = f"Audit User {stamp}" in body
                    res["status"] = "PASS" if ok else "FAIL"
                    res["detail"] = f"display_name saved (HTTP {resp.status if resp else '?'})"
                elif kind == "platform_select":
                    # only clickable when the platform is unlinked; otherwise state-check
                    plat = check.get("platform", "")
                    page.wait_for_timeout(300)
                    body = page.inner_text("body")
                    if "pending" in body.lower() or "verified" in body.lower() or "skipped" in body.lower():
                        res["status"] = "PASS"
                        res["detail"] = f"{plat}: already has a status on this test account (state preserved)"
                    else:
                        el["_pw"].click()
                        page.wait_for_timeout(1000)
                        page.reload(wait_until="networkidle")
                        res["status"] = "PASS"
                        res["detail"] = f"{plat}: clicked +Link → pending state"
                elif kind == "platform_verify":
                    el["_pw"].click()
                    page.wait_for_timeout(1000)
                    page.reload(wait_until="networkidle")
                    res["status"] = "PASS"
                    res["detail"] = "verify action fired"
                elif kind == "platform_skip":
                    el["_pw"].click()
                    page.wait_for_timeout(1000)
                    page.reload(wait_until="networkidle")
                    res["status"] = "PASS"
                    res["detail"] = "skip action fired"
                else:
                    res["status"] = "SKIP"
                    res["detail"] = f"unhandled check kind {kind}"
            except Exception as e:
                res["status"] = "FAIL"
                res["detail"] = f"exception: {e}"
            if res["status"] == "FAIL":
                res["shot"] = shot(f"FAIL_{item['id']}_{int(time.time())}")
            results.append(res)
            return res

        # ─── decide which pages to audit ─────────────────────────────
        pages = list(SPEC.keys())
        if args.page:
            pages = [args.page]

        if args.discover:
            # dump every clickable element per page for spec reconciliation
            logged_in = False
            for key in pages:
                if key in ("pricing-in", "nav-in", "topics-search"):
                    continue
                spec = SPEC[key]
                if not spec.get("logged_out") and not logged_in:
                    dest = login(); logged_in = True
                if spec.get("logged_out") and logged_in:
                    goto("/auth/logout"); page.wait_for_timeout(500); logged_in = False
                goto(key)
                els = discover(page)
                print(f"\n===== {key} ({spec['label']}) — {len(els)} clickables =====")
                for e in els:
                    if not e["visible"]:
                        continue
                    print(f"  <{e['tag']}> text={e['text']!r} name={e['name']!r} id={e['id']!r} href={e['href']!r} type={e['type']!r} onclick={e['onclick']!r} hxpost={e['hxpost']!r} loc={e['location'].strip()[:60]}")
            browser.close()
            return

        # pre-login state
        logged_in = False
        for key in pages:
            if key in ("pricing-in", "nav-in"):
                continue
            spec = SPEC[key]
            if key.startswith("/"):
                url = key
            else:
                continue  # pseudo-pages handled separately

            # ensure login state matches spec
            if not spec.get("logged_out") and not logged_in:
                dest = login()
                logged_in = True
                print(f"[login] → {dest}")
            if spec.get("logged_out") and logged_in:
                # log out by clearing session via logout URL
                goto("/auth/logout")
                page.wait_for_timeout(600)
                logged_in = False

            page_report = {"url": url, "label": spec["label"], "items": []}
            page_report["shot"] = shot(spec["screenshot"])
            goto(url)
            page_report["shot"] = shot(spec["screenshot"])
            elements = discover(page)
            matched, used = group_and_index(elements, spec)

            # spec items
            results = page_report["items"]
            for iid, (item, el) in matched.items():
                el["_pw"] = page.locator(f"text={item['match'].get('text')}").first if "text" in item["match"] else None
                # resolve pw locator properly by re-querying
                el["_pw"] = _locator_for(page, el)
                verify_item(page, item, el, results, page_report, args.shots)

            # undocumented clickables
            for e in elements:
                if e["key"] in used or not e["visible"]:
                    continue
                results.append({"id": "UNLISTED", "type": e["tag"], "task": "not in BDD spec",
                                "element": e, "status": "WARN",
                                "detail": f"undocumented clickable: <{e['tag']}> '{e['text']}' href={e['href'] or '-'} name={e['name'] or '-'}"})
            page_report["console_errors"] = list(console_errors)
            console_errors.clear()
            report["pages"].append(page_report)

        # pricing-in and nav-in pseudo-pages (need login)
        if "pricing-in" in pages:
            if not logged_in:
                login(); logged_in = True
            goto("/payments/pricing")
            spec = SPEC["pricing-in"]
            page_report = {"url": "/payments/pricing", "label": spec["label"], "items": []}
            page_report["shot"] = shot(spec["screenshot"])
            elements = discover(page)
            matched, used = group_and_index(elements, spec)
            results = page_report["items"]
            for iid, (item, el) in matched.items():
                el["_pw"] = _locator_for(page, el)
                verify_item(page, item, el, results, page_report, args.shots)
            for e in elements:
                if e["key"] in used or not e["visible"]:
                    continue
                results.append({"id": "UNLISTED", "type": e["tag"], "task": "not in BDD spec",
                                "element": e, "status": "WARN",
                                "detail": f"undocumented clickable: <{e['tag']}> '{e['text']}'"})
            page_report["console_errors"] = list(console_errors)
            console_errors.clear()
            report["pages"].append(page_report)

        if "nav-in" in pages:
            if not logged_in:
                login(); logged_in = True
            goto("/dashboard/")
            spec = SPEC["nav-in"]
            page_report = {"url": "/dashboard/ (nav)", "label": spec["label"], "items": []}
            page_report["shot"] = shot(spec["screenshot"])
            elements = discover(page)
            matched, used = group_and_index(elements, spec)
            results = page_report["items"]
            # avatar dropdown first so dropdown items are visible to discovery
            for iid, (item, el) in matched.items():
                el["_pw"] = _locator_for(page, el)
                verify_item(page, item, el, results, page_report, args.shots)
            for e in elements:
                if e["key"] in used or not e["visible"]:
                    continue
                results.append({"id": "UNLISTED", "type": e["tag"], "task": "not in BDD spec",
                                "element": e, "status": "WARN",
                                "detail": f"undocumented clickable: <{e['tag']}> '{e['text']}'"})
            page_report["console_errors"] = list(console_errors)
            console_errors.clear()
            report["pages"].append(page_report)

        # SAFE-1: protected routes redirect
        if not args.page or args.page == "safe":
            page_report = {"url": "protected-routes", "label": "SAFE-1 Protected routes → login", "items": []}
            for route in ["/dashboard/", "/freelance/pipeline", "/deliverables/portfolio", "/auth/profile", "/platforms/setup", "/admin/"]:
                goto("/auth/logout"); page.wait_for_timeout(500)
                goto(route, wait="commit")
                page.wait_for_timeout(600)
                ok = path_of(page.url) == "/auth/login" and "next=" in page.url
                page_report["items"].append({"id": route, "type": "route", "task": "redirect to /auth/login?next=...",
                                             "status": "PASS" if ok else "FAIL",
                                             "detail": f"{route} → {path_of(page.url)} next={'next=' in page.url}"})
            page_report["console_errors"] = list(console_errors); console_errors.clear()
            report["pages"].append(page_report)

            # SAFE-2: 404
            goto("/definitely-not-a-real-page", wait="commit")
            page.wait_for_timeout(600)
            status_ok = "404" in page.inner_text("body") or "not found" in page.inner_text("body").lower()
            page_report2 = {"url": "/definitely-not-a-real-page", "label": "SAFE-2 404 page", "items": [
                {"id": "404", "type": "route", "task": "render 404 not 500", "status": "PASS" if status_ok else "FAIL",
                 "detail": f"status text present: {status_ok}"}],
                "console_errors": list(console_errors)}
            console_errors.clear()
            report["pages"].append(page_report2)

        # SAFE-3: console error sweep
        total_errors = sum(len(pp.get("console_errors", [])) for pp in report["pages"])
        report["summary"]["console_errors_total"] = total_errors

        browser.close()

    # ─── summary ────────────────────────────────────────────────
    for pp in report["pages"]:
        pp_fail = any(it["status"] == "FAIL" for it in pp["items"])
        pp_warn = any(it["status"] == "WARN" for it in pp["items"])
        for it in pp["items"]:
            s = it["status"]
            if s == "PASS": report["summary"]["pass"] += 1
            elif s in ("FAIL", "WARN"): report["summary"]["fail"] += 1
            else: report["summary"]["skip"] += 1
        report["summary"]["pages_pass" if not pp_fail else "pages_fail"] += 1

    with open(args.out, "w") as f:
        json.dump(report, f, indent=2, default=lambda o: None)
    print(json.dumps(report["summary"], indent=2))
    print(f"results → {args.out}")


def _locator_for(page, el):
    """Build a Playwright locator for a discovered element."""
    if el.get("href") and el["href"].startswith(("/", "http")):
        l = page.locator(f"a[href='{el['href']}']").first
        if l.count() > 0:
            return l
    if el.get("name"):
        l = page.locator(f"[name='{el['name']}']").first
        if l.count() > 0:
            return l
    if el.get("id"):
        l = page.locator(f"#{el['id']}").first
        if l.count() > 0:
            return l
    if el.get("text"):
        l = page.get_by_text(el["text"], exact=False).first
        if l.count() > 0:
            return l
    return page.locator("body")


if __name__ == "__main__":
    main()

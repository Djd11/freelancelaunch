"""Dogfood harness — shared Playwright helpers for the first-run QA walkthrough.

Tester-only tooling. Nothing here touches app code; it drives the live server at
http://localhost:5000 and drops evidence (screenshots + network/console logs) into
docs/dogfood/.
"""
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("DOGFOOD_BASE", "http://localhost:5000")
ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / "shots"
ART = ROOT / "artifacts"
SHOTS.mkdir(parents=True, exist_ok=True)
ART.mkdir(parents=True, exist_ok=True)

STATE_FILE = ART / "state.json"


class Dogfood:
    """A browser session that records everything it sees."""

    def __init__(self, headless=True, viewport=(1440, 900)):
        self.t0 = time.time()
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=headless)
        ctx_kwargs = {"viewport": {"width": viewport[0], "height": viewport[1]}}
        if STATE_FILE.exists():
            ctx_kwargs["storage_state"] = str(STATE_FILE)
        self.ctx = self.browser.new_context(**ctx_kwargs)
        self.page = self.ctx.new_page()
        self.events = []          # console errors / page errors / bad responses
        self.timings = []         # per-navigation timing
        self._log_name = os.environ.get("DOGFOOD_LOG", "session")
        self.logf = open(ART / f"{self._log_name}.jsonl", "a")
        self._attach()

    # ---- recording -------------------------------------------------------
    def _attach(self):
        p = self.page

        p.on("console", lambda m: self._rec(
            "console", m.type, m.text,
            record=True) if m.type in ("error", "warning") else None)
        p.on("pageerror", lambda e: self._rec("pageerror", "error", str(e), record=True))
        p.on("requestfailed", lambda r: self._rec(
            "requestfailed", "error", f"{r.method} {r.url} :: {r.failure}", record=True))

        def _resp(r):
            try:
                if r.status >= 400:
                    self._rec("http", "error", f"{r.status} {r.request.method} {r.url}", record=True)
            except Exception:
                pass
        p.on("response", _resp)

    def _rec(self, kind, level, msg, record=False):
        entry = {"t": round(time.time() - self.t0, 2), "kind": kind, "level": level, "msg": msg[:600]}
        self.events.append(entry)
        if record:
            self.logf.write(json.dumps(entry) + "\n")
            self.logf.flush()

    # ---- helpers ---------------------------------------------------------
    def goto(self, path, wait=True, settle=400):
        url = path if path.startswith("http") else BASE + path
        t = time.time()
        try:
            resp = self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            status = resp.status if resp else None
        except Exception as e:
            self._rec("nav", "error", f"FAILED {url} :: {type(e).__name__}: {e}", record=True)
            return None
        self.timings.append({"url": url, "ms": round((time.time() - t) * 1000), "status": status})
        if status and status >= 400:
            self._rec("nav", "error", f"{status} on {url}", record=True)
        if settle:
            self.page.wait_for_timeout(settle)
        return status

    def shot(self, name, full=True):
        f = SHOTS / f"{name}.png"
        try:
            self.page.screenshot(path=str(f), full_page=full)
        except Exception as e:
            self._rec("shot", "error", f"{name}: {e}")
        return str(f)

    def text(self, sel="body"):
        try:
            return self.page.inner_text(sel)
        except Exception as e:
            return f"<no text: {e}>"

    def dump(self, name, limit=6000):
        """Save the visible text of the current page as evidence."""
        txt = self.text()[:limit]
        (ART / f"{name}.txt").write_text(
            f"URL: {self.page.url}\n--- visible text ---\n{txt}\n")
        return txt

    def links(self):
        return self.page.eval_on_selector_all(
            "a[href]", "els => els.map(e => ({t:(e.innerText||'').trim().slice(0,60), h:e.getAttribute('href')}))")

    def forms(self):
        return self.page.evaluate("""() => [...document.querySelectorAll('form')].map(f => ({
            action: f.getAttribute('action'), method: (f.method||'get').toUpperCase(),
            fields: [...f.querySelectorAll('input,select,textarea,button')].map(
              i => ({tag:i.tagName.toLowerCase(), name:i.name||null, type:i.type||null,
                     id:i.id||null, required:!!i.required, placeholder:i.placeholder||null}))}))""")

    def newtab(self):
        """Open a second, logged-out context to test authz."""
        p = self.ctx.new_page()
        return p

    def fresh_incognito(self):
        """A brand-new context with NO cookies (anonymous visitor)."""
        b = self.pw.chromium.launch(headless=True)
        c = b.new_context(viewport={"width": 1440, "height": 900})
        return b, c

    def save_state(self):
        self.ctx.storage_state(path=str(STATE_FILE))

    def note(self, msg):
        print(f"  • {msg}")

    def step(self, n, msg):
        print(f"\n[{n}] {msg}")

    def errors(self):
        return [e for e in self.events if e["level"] == "error"]

    def close(self):
        self.save_state()
        (ART / f"{self._log_name}.events.json").write_text(json.dumps(
            {"events": self.events, "timings": self.timings}, indent=1))
        self.logf.close()
        self.ctx.close()
        self.browser.close()
        self.pw.stop()


def uniq(prefix="dogfood"):
    return f"{prefix}{int(time.time())}"

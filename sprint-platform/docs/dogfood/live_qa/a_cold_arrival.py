"""Phase A: cold arrival as anonymous stranger. Records cold-start latency,
console errors, non-2xx responses, dead links on / and /topics + topic detail."""
import json, sys, time
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

BASE = "https://freelancelaunch.onrender.com"

def timed_goto(page, url):
    t0 = time.time()
    resp = page.goto(url, wait_until="domcontentloaded", timeout=90000)
    dt = time.time() - t0
    return resp, dt

def main():
    out = {"console_errors": [], "bad_responses": [], "timings": {}, "links": {}, "pages": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.on("console", lambda m: out["console_errors"].append({"page": page.url, "text": m.text}) if m.type == "error" else None)
        page.on("response", lambda r: out["bad_responses"].append({"url": r.url, "status": r.status, "page": page.url}) if r.status >= 400 else None)
        page.on("requestfailed", lambda r: out["bad_responses"].append({"url": r.url, "status": "FAILED", "page": page.url}))

        for name, path in [("landing", "/"), ("topics", "/topics"), ("health", "/health")]:
            resp, dt = timed_goto(page, BASE + path)
            out["timings"][name] = {"seconds": round(dt, 2), "status": resp.status if resp else None}
            time.sleep(1)

        # topic detail: grab first topic link
        page.goto(BASE + "/topics", wait_until="domcontentloaded", timeout=90000)
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
        topic_links = sorted({h for h in hrefs if h and h.startswith("/topics/")})
        out["pages"]["topics_topic_links"] = topic_links
        if topic_links:
            resp, dt = timed_goto(page, BASE + topic_links[0])
            out["timings"]["topic_detail"] = {"seconds": round(dt, 2), "status": resp.status if resp else None, "url": topic_links[0]}

        # collect all internal links from landing + topics + topic detail, HEAD them via page.request
        pages_to_scan = ["/", "/topics"] + topic_links[:3]
        all_links = set()
        for path in pages_to_scan:
            page.goto(urljoin(BASE, path), wait_until="domcontentloaded", timeout=90000)
            hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
            for h in hrefs:
                if not h or h.startswith("#") or h.startswith("mailto"):
                    continue
                u = urljoin(BASE, h)
                if urlparse(u).netloc == urlparse(BASE).netloc:
                    all_links.add(u)
            time.sleep(0.6)
        out["pages"]["internal_links_found"] = sorted(all_links)
        for u in sorted(all_links):
            try:
                r = page.request.head(u, timeout=90000)
                st = r.status
            except Exception as e:
                st = f"ERR {e}"
            out["links"][u] = st
            time.sleep(0.3)

        # landing page text for value-prop judgment
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=90000)
        out["pages"]["landing_text"] = page.inner_text("body")[:4000]
        page.goto(BASE + "/topics", wait_until="domcontentloaded", timeout=90000)
        out["pages"]["topics_text"] = page.inner_text("body")[:4000]
        if topic_links:
            page.goto(BASE + topic_links[0], wait_until="domcontentloaded", timeout=90000)
            out["pages"]["topic_detail_text"] = page.inner_text("body")[:4000]
            out["pages"]["topic_detail_url"] = BASE + topic_links[0]
        browser.close()
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main()

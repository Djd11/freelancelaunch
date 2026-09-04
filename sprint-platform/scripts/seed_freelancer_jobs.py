"""One-off seed: capture REAL live gigs from Freelancer.com skill pages.

Why not the REST API: /api/projects/0.1/projects/active/ silently ignores
query params without a JWT, and the search page is server-rendered only for
the generic latest feed. The per-skill listing pages
(https://www.freelancer.com/jobs/<skill>/) ARE server-rendered and genuinely
filtered ("Latest Klaviyo Jobs" etc.) — so we render those with headless
Chromium and extract the project cards. Output: scripts/freelancer_seed.json
consumed by scripts/apply_freelancer_seed.py.

Run:  .venv/bin/python scripts/seed_freelancer_jobs.py
"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

CLUSTER_SKILLS = {
    "email-automation": ["klaviyo", "mailchimp", "email-marketing", "hubspot", "n8n", "zapier", "email-automation"],
    "web-scraping": ["web-scraping", "data-mining", "selenium", "python", "data-capture"],
    "ai-chatbots": ["chatbot-development", "ai-development", "openai", "whatsapp", "gpt-4"],
}
OUT = Path(__file__).resolve().parent / "freelancer_seed.json"

CARD_JS = """() => {
  const out = [];
  for (const a of document.querySelectorAll("a[href*='/projects/']")) {
    const href = a.getAttribute("href") || "";
    if (!/^\\/projects\\/[a-z0-9-]+\\/[a-z0-9-]+/.test(href)) continue;
    const card = a.closest("div,li") || a;
    const txt = (card.innerText || "").replace(/\\u00a0/g, " ").trim();
    if (txt.length < 15) continue;
    out.push({href, txt: txt.slice(0, 800)});
  }
  return out;
}"""


def parse_card(card, cluster, skill):
    lines = [l.strip() for l in card["txt"].split("\n") if l.strip()]
    title = lines[0] if lines else ""
    blob = " | ".join(lines)
    m = re.search(r"[$€£]\s?([\d,]+)\s*(?:[–-]\s*([\d,]+))?", blob)
    rate = None
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", "")) if m.group(2) else lo
        rate = (lo + hi) / 2
    # bids like "48 bids"
    mb = re.search(r"(\d+)\s*bids?", blob, re.I)
    bids = int(mb.group(1)) if mb else None
    mt = re.search(r"(\d+)\s*(?:days?|hours?|mins?)\s*(?:left|ago)", blob, re.I)
    return {
        "cluster": cluster, "skill": skill, "title": title[:200],
        "url": "https://www.freelancer.com" + card["href"],
        "rate": rate, "bids": bids, "age": mt.group(0) if mt else "",
        "description": blob[:2000],
    }


def main():
    collected = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()
        for cluster, skills in CLUSTER_SKILLS.items():
            collected.setdefault(cluster, {})
            for skill in skills:
                try:
                    page.goto(f"https://www.freelancer.com/jobs/{skill}/",
                              wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3500)
                    page.mouse.wheel(0, 2500)  # lazy-load more cards
                    page.wait_for_timeout(1500)
                    cards = page.evaluate(CARD_JS)
                except Exception as exc:
                    print(f"{cluster}/{skill}: FAILED {exc}")
                    continue
                n = 0
                for c in cards:
                    job = parse_card(c, cluster, skill)
                    if not job["title"] or job["url"] in collected[cluster]:
                        continue
                    collected[cluster][job["url"]] = job
                    n += 1
                print(f"{cluster}/{skill}: {n} new (total {len(collected[cluster])})")
        b.close()
    out = [j for d in collected.values() for j in d.values()]
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {len(out)} real gigs -> {OUT}")


if __name__ == "__main__":
    main()

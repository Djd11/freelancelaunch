"""Pricing config — single source of truth for the freemium + one-time-per-sprint
model. Prices, tiers, and Stripe Payment Link env vars live here so the pricing
page, landing copy, structured data, and llms.txt never drift.

Model (chosen for launch):
  Free Preview   -> Day 1 + live demand readout (no card)
  Full Sprint    -> $99 one-time   (launch offer $49 for the first cohort)
  Sprint + Mentor-> $199 one-time

Payments are collected via Stripe Payment Links (env-configured). Content is NOT
gated in v1: starting a sprint opens the free preview, and the paid Enroll
buttons point at the configured checkout link.
"""
import os

CURRENCY = "USD"
LAUNCH_PRICE = 49  # first-cohort launch offer for the Full Sprint

TIERS = [
    {
        "key": "preview",
        "name": "Free Preview",
        "price": 0,
        "blurb": "Test-drive Day 1 and see the real demand for your skill.",
        "features": [
            "Day 1 lesson + sprint orientation",
            "Live job-demand readout for your cluster",
            "No card required",
        ],
        "cta": "Start free preview",
        "link_env": None,
    },
    {
        "key": "full",
        "name": "Full Sprint",
        "price": 99,
        "blurb": "The complete 14-day demand-validated sprint, one-time.",
        "features": [
            "All 14 days · 3 phases (Skill → Mock Contract → Send Proposals)",
            "Mock Contract verification + Demand-Validated badge",
            "Job Unlock Meter + live job feed",
            "LLM-engineered proposal builder",
        ],
        "cta": "Enroll — $99",
        "link_env": "STRIPE_LINK_FULL",
        "popular": True,
    },
    {
        "key": "mentor",
        "name": "Sprint + Mentor",
        "price": 199,
        "blurb": "Everything in Full Sprint, plus a human in your corner.",
        "features": [
            "Everything in Full Sprint",
            "Human mentor review of your Mock Contract",
            "1 live Q&A session",
            "Personalised proposal critique",
        ],
        "cta": "Enroll — $199",
        "link_env": "STRIPE_LINK_MENTOR",
    },
]


def standard_price():
    """Headline price used in structured data (the Full Sprint)."""
    return next((t["price"] for t in TIERS if t["key"] == "full"), 99)


def resolved_tiers():
    """TIERS with an href resolved from env. Falls back to /sprints so a button
    is never broken before the Stripe Payment Link is configured."""
    out = []
    for t in TIERS:
        tt = dict(t)
        env = t.get("link_env")
        link = os.getenv(env) if env else None
        tt["href"] = link or "/sprints"
        tt["configured"] = bool(link)
        out.append(tt)
    return out

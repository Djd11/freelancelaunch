"""main blueprint — landing, sprint picker, request-a-sprint, pricing (arch §4.2)."""
import datetime
import os
import threading

from flask import Blueprint, render_template, request, redirect, url_for, g, current_app

from routes import require_login, load_cluster
from services.sprint_planner import create_plan
from services.copywork_engine import create_projects
from services.lesson_engine import generate_sprint_content
from . import obtain_supabase

main_bp = Blueprint("main", __name__)

# Empty-state shape for the landing counter card when no active clusters exist
# yet. Numbers are never fabricated — every counter shown on the landing page
# comes from job_clusters (eng-spec J1/J2 acceptance).
EMPTY_FEATURED = {
    "job_count": 0, "avg_rate": 0, "growth_score": 0, "display_name": "—",
}


def _active_clusters(sb):
    rows = sb.table("job_clusters").select("*").eq("status", "active").execute().data
    return sorted(rows, key=lambda r: (r.get("job_count") or 0), reverse=True)


def _open_cohort(sb, cluster_key):
    """Open a new active cohort for the cluster. Idempotent: if an active
    cohort already exists, return it instead of creating a duplicate."""
    existing = sb.table("cohorts").select("id") \
        .eq("cluster_key", cluster_key).eq("status", "active") \
        .limit(1).execute().data
    if existing:
        return existing[0]["id"]

    today = datetime.date.today()
    count = sb.table("cohorts").select("id").eq("cluster_key", cluster_key).execute().data
    row = sb.table("cohorts").insert({
        "cluster_key": cluster_key,
        "name": f"Cohort #{len(count) + 1}",
        "start_date": today.isoformat(),
        "end_date": (today + datetime.timedelta(days=13)).isoformat(),
        "status": "active",
    }).execute().data[0]
    return row["id"]


@main_bp.route("/")
def index():
    sb = obtain_supabase()
    clusters = _active_clusters(sb)
    featured = clusters[0] if clusters else EMPTY_FEATURED
    return render_template("landing.html", featured=featured, clusters=clusters)


@main_bp.route("/topics")
def topics():
    """Public topics index — one card per ACTIVE demand-validated cluster.
    Each card links to a per-cluster detail page so crawlers (Google +
    agentic/AI) can surface individual sprint topics instead of a dead-end
    redirect to the auth-gated picker."""
    sb = obtain_supabase()
    clusters = _active_clusters(sb)
    return render_template("topics.html", clusters=clusters)


@main_bp.route("/topics/<cluster_key>")
def topic_detail(cluster_key):
    """Public per-cluster detail page with a scoped Course JSON-LD block.

    Renders the cluster's display_name, icon, description, promise and live
    demand stats so the page carries unique, meaningful content for search.
    Unknown cluster keys 404 back to the topics index."""
    sb = obtain_supabase()
    cluster = load_cluster(sb, cluster_key)
    if not cluster:
        return redirect(url_for("main.topics"))
    return render_template("topic_detail.html", cluster=cluster)


@main_bp.route("/sprints")
def sprints():
    # Public: crawlers must see the full catalog (Course ItemList JSON-LD).
    # The template renders a login link for anonymous visitors instead of the
    # POST form (start_sprint stays auth-gated).
    sb = obtain_supabase()
    clusters = _active_clusters(sb)
    return render_template("sprint_picker.html", clusters=clusters)


@main_bp.route("/sprints/request", methods=["POST"])
def request_sprint():
    gate = require_login()
    if gate:
        return gate
    skill = request.form.get("skill", "").strip().lower().replace(" ", "-")
    if skill:
        sb = obtain_supabase()
        existing = sb.table("job_clusters").select("*").eq("cluster_key", skill).limit(1).execute().data
        if not existing:
            sb.table("job_clusters").insert({
                "cluster_key": skill,
                "display_name": skill.replace("-", " ").title(),
                "icon": "🔎",
                "description": "Requested — we curate the live demand feed before we build it.",
                "job_count": 0,
                "avg_rate": 0,
                "growth_score": 0,
                "status": "requested",
            }).execute()
    return redirect(url_for("main.sprints"))


@main_bp.route("/sprints/<cluster_key>/start", methods=["POST"])
def start_sprint(cluster_key):
    """Enroll: create or resume a sprint for the cluster (idempotent).
    If user already has an active sprint for this cluster, redirect to it.
    Otherwise create a new sprint with plan + projects + background generation.
    """
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    cluster = sb.table("job_clusters").select("*").eq("cluster_key", cluster_key).limit(1).execute().data
    if not cluster:
        return redirect(url_for("main.sprints"))
    cluster = cluster[0]
    user_id = g.user["id"]

    # Idempotent: check for existing active sprint for this user + cluster
    existing = sb.table("sprints").select("id,current_day,status") \
        .eq("user_id", user_id).eq("cluster_key", cluster_key).eq("status", "active") \
        .order("started_at", desc=True).limit(1).execute().data
    if existing:
        existing_sprint_id = existing[0]["id"]
        return redirect(url_for("sprints.dashboard", sprint_id=existing_sprint_id))

    # Join the latest active cohort for this cluster, else open a new one.
    cohort = sb.table("cohorts").select("*").eq("cluster_key", cluster_key).eq("status", "active").limit(1).execute().data
    cohort_id = cohort[0]["id"] if cohort else _open_cohort(sb, cluster_key)

    sprint = sb.table("sprints").insert({
        "user_id": user_id,
        "cohort_id": cohort_id,
        "cluster_key": cluster_key,
        "phase": "A",
        "current_day": 1,
        "status": "active",
    }).execute().data[0]

    # Skeleton first (fast, always works), then LLM content fills in async —
    # the request never waits on the LLM (eng-spec §5: async generation, DB
    # progress log, frontend polling). Each sprint_days payload the worker
    # populates IS the progress the dashboard polls.
    create_plan(sb, sprint["id"])
    create_projects(sb, sprint["id"])
    sb.table("sprint_unlock_snapshots").upsert({
        "sprint_id": sprint["id"], "user_id": user_id,
        "completed_days": 0, "unlocked_count": 0, "total_in_cluster": 0, "last_delta": 0,
    }, on_conflict="sprint_id,user_id").execute()

    app = current_app._get_current_object()
    threading.Thread(
        target=_generate_in_background, args=(app, sprint["id"],), daemon=True,
    ).start()
    return redirect(url_for("sprints.dashboard", sprint_id=sprint["id"]))


def _generate_in_background(app, sprint_id):
    """Background LLM content generation — stamps visible errors on failure."""
    from services.lesson_engine import start_generation, stop_generation
    start_generation(sprint_id)
    try:
        with app.app_context():
            try:
                from supabase import create_client
                sb = create_client(
                    app.config.get("SUPABASE_URL") or "",
                    app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
                )
                generate_sprint_content(sb, sprint_id)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).exception("lesson generation failed for %s", sprint_id)
                # Stamp generation_error on the first empty day so the UI surfaces it
                try:
                    sb2 = create_client(
                        app.config.get("SUPABASE_URL") or "",
                        app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
                    )
                    days = sb2.table("sprint_days").select("day_no, action_payload") \
                        .eq("sprint_id", sprint_id).order("day_no").execute().data
                    for d in (days or []):
                        payload = d.get("action_payload") or {}
                        if not payload.get("lesson"):
                            payload["generation_error"] = f"Generation failed: {exc}"
                            sb2.table("sprint_days").update({"action_payload": payload}) \
                                .eq("sprint_id", sprint_id).eq("day_no", d["day_no"]).execute()
                            break
                except Exception:
                    logging.getLogger(__name__).exception("failed to stamp generation_error for %s", sprint_id)
    finally:
        stop_generation(sprint_id)


@main_bp.route("/robots.txt")
def robots_txt():
    """Robots with sitemap reference (SEO: crawlability + discovery)."""
    base = (os.getenv("PUBLIC_BASE_URL") or request.host_url).rstrip("/")
    lines = ["User-agent: *",
             "Disallow: /sprints/",   # auth-gated learner content
             "Disallow: /mentor",     # auth-gated
             "Disallow: /profile",    # auth-gated
             "Disallow: /admin",      # internal ops
             "Allow: /"]
    lines.append(f"\nSitemap: {base}/sitemap.xml")
    body = "\n".join(lines) + "\n"
    return body, 200, {"Content-Type": "text/plain; charset=utf-8"}


@main_bp.route("/sitemap.xml")
def sitemap_xml():
    """XML sitemap for the public, indexable pages (SEO: systematic crawling).

    Static public routes + one URL per ACTIVE cluster (each per-cluster topic
    detail page is a distinct "course" surface). Lastmod is left off —
    the job counts change daily and we don't want stale timestamps lying
    to crawlers.
    """
    base = (os.getenv("PUBLIC_BASE_URL") or request.host_url).rstrip("/")

    urls = [
        ("/", "1.0", "weekly"),
        ("/sprints", "0.9", "daily"),      # picker: live job counts
        ("/topics", "0.9", "daily"),        # topics index
        ("/pricing", "0.6", "monthly"),
        ("/clients/freelancers", "0.7", "daily"),
    ]
    items = [
        "  <url>\n"
        f"    <loc>{base}{loc}</loc>\n"
        f"    <changefreq>{freq}</changefreq>\n"
        f"    <priority>{prio}</priority>\n"
        "  </url>"
        for loc, prio, freq in urls
    ]

    # One URL per ACTIVE cluster — each has its own topic detail page.
    try:
        sb = obtain_supabase()
        clusters = _active_clusters(sb)
        for c in clusters:
            key = c.get("cluster_key")
            if key:
                items.append(
                    "  <url>\n"
                    f"    <loc>{base}/topics/{key}</loc>\n"
                    "    <changefreq>daily</changefreq>\n"
                    "    <priority>0.8</priority>\n"
                    "  </url>"
                )
    except Exception:
        # If Supabase fails, still emit the static URLs above.
        pass

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(items)
        + "\n</urlset>"
    )
    return body, 200, {"Content-Type": "application/xml; charset=utf-8"}


@main_bp.route("/llms.txt")
def llms_txt():
    """Plain-text site map for AI crawlers (llms.txt, https://llmstxt.org/).

    A short, factual summary + the key public surfaces so agentic/AI search
    (ChatGPT, Perplexity, Gemini, Claude, Google AI Overviews) can discover
    and cite the site. Relative URLs — crawlers resolve them against this
    file's location.
    """
    lines = [
        "# FreelanceLaunch",
        "> FreelanceLaunch runs 14-day demand-validated freelance sprints: copy-work skill acquisition, a mock contract, and engineered proposals against a live job feed.",
        "",
        "## Courses",
        "- /sprints : All demand-validated sprint topics — each built against a live job cluster",
        "- /topics : Sprint topic index with live job counts, median rates, and demand growth",
    ]
    # One line per ACTIVE cluster so AI crawlers can name specific topics.
    try:
        sb = obtain_supabase()
        for c in _active_clusters(sb):
            key = c.get("cluster_key")
            name = c.get("display_name") or key
            if key:
                lines.append(f"- /topics/{key} : {name} — 14-day demand-validated sprint")
    except Exception:
        # Static lines above are always served even if Supabase is down.
        pass
    lines += [
        "",
        "## How it works",
        "- / : Landing — the 14-day demand-validated sprint explained",
        "- /pricing : Free during v1",
        "- /clients/freelancers : How freelancers find and land clients",
    ]
    body = "\n".join(lines) + "\n"
    return body, 200, {"Content-Type": "text/plain; charset=utf-8"}


@main_bp.route("/pricing")
def pricing():
    return render_template("pricing.html")


@main_bp.route("/dashboard/")
def dashboard():
    """The sprint dashboard landing — redirects to the user's sprint picker."""
    gate = require_login()
    if gate:
        return gate
    return redirect(url_for("main.sprints"))

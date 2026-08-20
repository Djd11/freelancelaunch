"""
Sprint Platform — Flask application factory.
Blueprints mirror architecture.md §4.2. All data lives in the dedicated
Supabase project (services/supabase_client.py) — no in-memory fallback.
"""
import os
import logging

from flask import Flask, g, session, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object("config.Config")
    if test_config:
        app.config.update(test_config)
    csrf.init_app(app)

    from routes.main import main_bp
    from routes.sprints import sprints_bp
    from routes.contract import contract_bp
    from routes.proposals import proposals_bp
    from routes.profile import profile_bp
    from routes.mentor import mentor_bp
    from routes.clients import clients_bp
    from routes.auth import auth_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(sprints_bp)
    app.register_blueprint(contract_bp)
    app.register_blueprint(proposals_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(mentor_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(admin_bp)

    @app.before_request
    def load_user():
        g.user = None
        user_id = session.get("user_id")
        if user_id:
            from services.supabase_client import get_supabase
            # Sessions must reference a real auth.users UUID. A stale
            # non-UUID id would pass load_user but crash the first uuid-FK
            # write (Postgres 22P02) — drop it here.
            import uuid as _uuid
            try:
                _uuid.UUID(user_id)
            except (ValueError, AttributeError, TypeError):
                session.pop("user_id", None)
                return
            sb = get_supabase()
            try:
                resp = sb.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
                if resp.data:
                    g.user = resp.data[0]
                    g.user["id"] = user_id
                else:
                    # Session is enough for auth-gated routes; profile is optional.
                    g.user = {"user_id": user_id, "display_name": user_id, "id": user_id}
            except Exception:
                g.user = {"user_id": user_id, "display_name": user_id, "id": user_id}

    @app.context_processor
    def inject_globals():
        return {"user": g.get("user")}

    @app.route("/favicon.ico")
    def favicon():
        # Chrome requests /favicon.ico regardless of the inline data-URI icon
        # after form-POST navigations — serve the real file so no 404 shows.
        return app.send_static_file("favicon.ico")

    @app.route("/health")
    def health():
        from services.supabase_client import get_supabase
        try:
            db = get_supabase()
        except Exception as exc:
            return {
                "status": "error",
                "mode": "supabase",
                "error": str(exc),
            }, 503
        # Ping a public marketing table so we know RLS + schema are up.
        try:
            ping = db.table("job_clusters").select("cluster_key").limit(1).execute()
            return {
                "status": "ok",
                "mode": "supabase",
                "tables": "live",
                "project": (app.config.get("SUPABASE_URL") or "").split("//")[-1],
                "clusters_reachable": True,
                "sample_count": len(ping.data or []),
            }
        except Exception as exc:
            return {
                "status": "error",
                "mode": "supabase",
                "tables": "live",
                "project": (app.config.get("SUPABASE_URL") or "").split("//")[-1],
                "clusters_reachable": False,
                "error": str(exc),
            }, 503

    @app.template_filter("money")
    def money(value):
        try:
            return f"${int(value)}"
        except (TypeError, ValueError):
            return f"${value}"

    @app.template_filter("dt")
    def dt(value):
        if not value:
            return ""
        return str(value)[:10]

    @app.template_filter("format_script")
    def format_script(text):
        """Render a lesson script as readable HTML.

        The LLM produces scripts with:
        - Numbered steps: ``1. Step text``
        - Bold: ``**text**``
        - Sub-bullets: ``- item``
        - Paragraph breaks: blank lines

        This filter converts them to semantic HTML so the page is
        scannable instead of a wall of unformatted text.
        """
        import re, markupsafe
        if not text:
            return markupsafe.Markup("")

        # Some generated lessons store literal escape sequences ("\\n") instead
        # of real line breaks (the model double-escaped the JSON). Normalize
        # them first so line-based parsing below actually splits on paragraphs.
        text = str(text).replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")

        lines = text.split("\n")
        html_parts = []
        in_ol = False
        in_ul = False

        def close_lists():
            nonlocal in_ol, in_ul
            parts = []
            if in_ol:
                parts.append("</ol>")
                in_ol = False
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            return parts

        for line in lines:
            stripped = line.strip()

            # Blank line → paragraph break
            if not stripped:
                html_parts.extend(close_lists())
                html_parts.append("<br>")
                continue

            # Numbered step: "1. Step text" or "10. Step text"
            ol_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
            if ol_match:
                if in_ul:
                    html_parts.extend(close_lists())
                if not in_ol:
                    html_parts.append("<ol style='margin:8px 0 8px 20px;padding:0'>")
                    in_ol = True
                step_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", ol_match.group(2))
                html_parts.append(f"<li style='margin-bottom:6px;line-height:1.5'>{step_text}</li>")
                continue

            # Sub-bullet: "- item" or "* item"
            ul_match = re.match(r"^[-*]\s+(.+)$", stripped)
            if ul_match:
                html_parts.extend(close_lists())
                if not in_ul:
                    html_parts.append("<ul style='margin:4px 0 4px 20px;padding:0'>")
                    in_ul = True
                bullet_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", ul_match.group(1))
                html_parts.append(f"<li style='margin-bottom:3px;line-height:1.5'>{bullet_text}</li>")
                continue

            # Indented sub-step (e.g. "  - item" or "  * item")
            indented_match = re.match(r"^\s{2,}[-*]\s+(.+)$", line)
            if indented_match:
                html_parts.extend(close_lists())
                if not in_ul:
                    html_parts.append("<ul style='margin:4px 0 4px 36px;padding:0'>")
                    in_ul = True
                bullet_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", indented_match.group(1))
                html_parts.append(f"<li style='margin-bottom:2px;line-height:1.5;list-style:circle'>{bullet_text}</li>")
                continue

            # Plain paragraph text
            html_parts.extend(close_lists())
            para_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", stripped)
            html_parts.append(f"<p style='margin:6px 0;line-height:1.6'>{para_text}</p>")

        html_parts.extend(close_lists())
        return markupsafe.Markup("\n".join(html_parts))

    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    create_app().run(host="127.0.0.1", port=port, debug=True)

"""
Sprint Platform — Flask application factory.
Blueprints mirror architecture.md §4.2. In DEV mode (no SUPABASE_URL) the app
serves from an in-memory FakeSupabase so localhost renders the mockup 1:1.
"""
import os
import logging

from flask import Flask, g, session, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object("config.Config")
    if test_config:
        app.config.update(test_config)

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
            from services.supabase_client import get_supabase, is_live_configured
            # Live mode: sessions must reference a real auth.users UUID. A
            # stale dev-mode id ("demo-user") would pass load_user but crash
            # the first uuid-FK write (Postgres 22P02) — drop it here.
            if is_live_configured(app.config):
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

    @app.route("/health")
    def health():
        from services.supabase_client import get_supabase, is_live_configured
        live = is_live_configured(app.config)
        try:
            db = get_supabase()
        except Exception as exc:
            return {
                "status": "error",
                "mode": "supabase" if live else "dev-fake",
                "error": str(exc),
            }, 503
        if hasattr(db, "_data"):
            return {
                "status": "ok",
                "mode": "dev-fake",
                "tables": sorted(list(db._data.keys())),
            }
        # Live client: ping a public marketing table so we know RLS + schema are up.
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

    return app


if __name__ == "__main__":
    from services.supabase_client import get_dev_db
    from services.seed_demo import seed_demo
    db = get_dev_db()
    if not db.rows("job_clusters"):
        seed_demo(db)
    port = int(os.getenv("PORT", 5000))
    create_app().run(host="127.0.0.1", port=port, debug=True)

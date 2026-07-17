"""
FreelanceLaunch — Main Application
"""
import os
from flask import Flask, redirect, url_for, render_template, session, g
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    
# ─── Import route blueprints ───────────────────────────────
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    from routes.auth import auth_bp
    from routes.topics import topics_bp
    from routes.dashboard import dashboard_bp
    from routes.progress import progress_bp
    from routes.deliverables import deliverables_bp
    from routes.freelance import freelance_bp
    from routes.payments import payments_bp
    from routes.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(topics_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(progress_bp)
    app.register_blueprint(deliverables_bp)
    app.register_blueprint(freelance_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(admin_bp)
    
    # ─── Inject user into all templates ────────────────────────
    @app.before_request
    def load_user():
        g.user = None
        user_id = session.get("user_id")
        if user_id:
            from services.supabase_client import get_supabase
            sb = get_supabase()
            resp = sb.table("user_profiles").select("*, auth.users(email)").eq("user_id", user_id).limit(1).execute()
            if resp.data:
                g.user = resp.data[0]
                g.user["id"] = user_id  # ensure user_id is accessible
    
    @app.context_processor
    def inject_globals():
        return {
            "user": g.get("user"),
            "STRIPE_PUBLISHABLE_KEY": app.config.get("STRIPE_PUBLISHABLE_KEY", ""),
        }
    
    # ─── Routes ────────────────────────────────────────────────
    from routes.topics import CURATED_TOPICS
    
    @app.route("/")
    def index():
        if g.user:
            return redirect(url_for("dashboard.home"))
        return render_template("landing.html", topics=CURATED_TOPICS)
    
    @app.route("/health")
    def health():
        return {"status": "ok", "env_set": bool(app.config.get("SUPABASE_URL"))}
    
    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

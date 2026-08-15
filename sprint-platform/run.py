"""Localhost dev server — renders the mockup 1:1 with zero DB setup."""
import os

from app import create_app
from services.supabase_client import get_dev_db
from services.seed_demo import seed_demo

db = get_dev_db()
if not db.rows("job_clusters"):
    seed_demo(db)

app = create_app()
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)

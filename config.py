"""
FreelanceLaunch — Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # LLM (uses Hermes-style config or env fallback)
    LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:3002/v1/chat/completions")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    # Stripe
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # Gumroad (fallback for MVP payments)
    GUMROAD_TOKEN = os.getenv("GUMROAD_TOKEN", "")
    
    # YouTube Data API
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
    
    # Video pipeline
    REMOTION_PROJECT_DIR = os.getenv(
        "REMOTION_PROJECT_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video-pipeline")
    )
    
    # Render hosting
    RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:5000")
    
    # Cohort defaults
    DEFAULT_COHORT_DAYS = 30
    COHORT_START_DAY = 1  # 1st of month
    COHORT_START_DAY_ALT = 15  # 15th of month

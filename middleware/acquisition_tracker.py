"""
Acquisition tracker middleware — Funnel 1: track where users come from
"""
from flask import request, g
from services.supabase_client import get_supabase
import uuid


class AcquisitionTracker:
    """
    Tracks user acquisition sources.
    Call track_visit() on landing page visits to capture source data.
    """
    
    @staticmethod
    def track_visit():
        """Capture the source of a visit (before user is logged in)."""
        source = request.args.get("source", "direct")
        ref = request.args.get("ref", "")
        utm_source = request.args.get("utm_source", "")
        utm_campaign = request.args.get("utm_campaign", "")
        utm_medium = request.args.get("utm_medium", "")
        topic = request.args.get("topic", "")
        
        # Store in session so we can associate with user on signup
        if not hasattr(g, 'acquisition_data'):
            g.acquisition_data = {
                "source": source,
                "source_detail": ref,
                "utm_source": utm_source,
                "utm_campaign": utm_campaign,
                "utm_medium": utm_medium,
                "landing_topic": topic,
            }
    
    @staticmethod
    def get_acquisition_data():
        """Get stored acquisition data."""
        return getattr(g, 'acquisition_data', {
            "source": "direct",
            "source_detail": "",
            "landing_topic": "",
        })

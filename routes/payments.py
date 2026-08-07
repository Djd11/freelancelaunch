"""
Payments routes — Stripe integration for paid tiers
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from services.supabase_client import get_supabase
import stripe
import os

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


TIERS = {
    "free": {
        "name": "Free",
        "price": 0,
        "features": ["Full curriculum access", "Community Discord", "Progress tracking"]
    },
    "guided": {
        "name": "Guided Accelerator",
        "price": 49,
        "features": [
            "Everything in Free",
            "Daily accountability check-ins",
            "Proposal reviews (up to 5)",
            "Private cohort community",
            "Job application tracker"
        ],
        "stripe_price_id": os.getenv("STRIPE_GUIDED_PRICE_ID", "")
    },
    "placement": {
        "name": "Placement Program",
        "price": 199,
        "features": [
            "Everything in Guided",
            "2x 1-on-1 mentor sessions",
            "Profile optimization (Upwork/Fiverr rewrite)",
            "3 direct client introductions",
            "90-day post-program support"
        ],
        "stripe_price_id": os.getenv("STRIPE_PLACEMENT_PRICE_ID", "")
    }
}


@payments_bp.route("/pricing")
def pricing():
    return render_template("pricing.html", tiers=TIERS)


@payments_bp.route("/create-checkout", methods=["POST"])
def create_checkout():
    """Create a Stripe Checkout Session for paid tiers."""
    if not g.user:
        return jsonify({"error": "Not logged in"}), 401
    
    tier = request.form.get("tier", "")
    if tier not in ("guided", "placement"):
        flash("Invalid tier", "error")
        return redirect(url_for("payments.pricing"))
    
    tier_config = TIERS[tier]
    
    # If Stripe is configured, create checkout session
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if stripe_key and tier_config.get("stripe_price_id"):
        stripe.api_key = stripe_key
        try:
            checkout = stripe.checkout.Session.create(
                mode="payment",
                line_items=[{
                    "price": tier_config["stripe_price_id"],
                    "quantity": 1,
                }],
                success_url=request.host_url + "payments/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=request.host_url + "payments/pricing",
                customer_email=g.user.get("avatar_url", ""),  # avatar_url stores the signup email
                metadata={
                    "user_id": g.user["id"],
                    "tier": tier,
                }
            )
            return redirect(checkout.url)
        except Exception as e:
            flash(f"Payment error: {str(e)}", "error")
            return redirect(url_for("payments.pricing"))
    
    # Fallback to Gumroad (manual redirect)
    gumroad_links = {
        "guided": os.getenv("GUMROAD_GUIDED_URL", ""),
        "placement": os.getenv("GUMROAD_PLACEMENT_URL", ""),
    }
    gumroad_url = gumroad_links.get(tier)
    if gumroad_url:
        return redirect(gumroad_url)
    
    flash("Payment not configured yet. Contact support.", "error")
    return redirect(url_for("payments.pricing"))


@payments_bp.route("/success")
def payment_success():
    """Handle successful payment redirect.

    The paid tier is granted ONLY after the Stripe session is verified to be
    real, paid, and owned by the current user. A missing / unverifiable /
    unpaid / foreign session_id is a hard error — never a silent upgrade
    (previously GET /payments/success with no session_id granted the $49
    Guided tier for free).
    """
    if not g.user:
        return redirect(url_for("auth.login"))

    session_id = request.args.get("session_id", "")
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not (stripe_key and session_id):
        flash("We couldn't verify your payment. Contact support.", "error")
        return redirect(url_for("payments.pricing"))

    try:
        stripe.api_key = stripe_key
        checkout = stripe.checkout.Session.retrieve(session_id)
        if checkout.payment_status != "paid":
            flash("Payment not completed yet. Contact support.", "error")
            return redirect(url_for("payments.pricing"))
        if checkout.metadata.get("user_id") != g.user["id"]:
            flash("This payment session doesn't match your account.", "error")
            return redirect(url_for("payments.pricing"))
        tier = checkout.metadata.get("tier", "guided")
        if tier not in TIERS or tier == "free":
            tier = "guided"
    except Exception:
        flash("Payment verification failed. Contact support.", "error")
        return redirect(url_for("payments.pricing"))

    # Upgrade user in database
    sb = get_supabase()
    sb.table("user_profiles").update({
        "tier": tier,
        "updated_at": "now()"
    }).eq("user_id", g.user["id"]).execute()

    sb.table("user_acquisition").update({
        "tier": tier,
        "converted_to_paid_at": "now()"
    }).eq("user_id", g.user["id"]).execute()

    flash(f"Welcome to {TIERS[tier]['name']}! You now have access to premium features.", "success")
    return redirect(url_for("dashboard.home"))

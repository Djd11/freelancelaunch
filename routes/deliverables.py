"""
Deliverables routes — user submissions and portfolio
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from services.supabase_client import get_supabase

deliverables_bp = Blueprint("deliverables", __name__, url_prefix="/deliverables")


@deliverables_bp.route("/submit", methods=["GET", "POST"])
def submit():
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    if request.method == "POST":
        day_number = request.form.get("day_number", type=int)
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        del_type = request.form.get("type", "other")
        
        if not day_number:
            flash("Day number is required", "error")
        
        sb.table("deliverables").insert({
            "user_id": user_id,
            "day_number": day_number,
            "type": del_type,
            "title": title or f"Day {day_number} Deliverable",
            "content": content,
        }).execute()
        
        flash("Deliverable submitted! Add it to your portfolio when reviewed.", "success")
        return redirect(url_for("dashboard.home"))
    
    day = request.args.get("day", type=int)
    return render_template("dashboard/submit.html", day=day)


@deliverables_bp.route("/portfolio")
def portfolio():
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    resp = sb.table("deliverables").select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(50) \
        .execute()
    
    deliverables = resp.data if resp.data else []
    
    return render_template("dashboard/portfolio.html", deliverables=deliverables)

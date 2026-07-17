"""
Freelance Pipeline routes — Funnel 2: track proposals → contracts → payments
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from services.supabase_client import get_supabase
from datetime import date

freelance_bp = Blueprint("freelance", __name__, url_prefix="/freelance")


@freelance_bp.route("/pipeline")
def pipeline():
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    # Get all pipelines for this user
    pipelines = sb.table("freelance_pipeline").select("*") \
        .eq("user_id", user_id) \
        .order("updated_at", desc=True) \
        .execute()
    
    # Get contracts
    contracts = sb.table("contracts").select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(20) \
        .execute()
    
    return render_template("dashboard/pipeline.html",
        pipelines=pipelines.data or [],
        contracts=contracts.data or []
    )


@freelance_bp.route("/api/update", methods=["POST"])
def update_pipeline():
    """Update pipeline stage or stats."""
    if not g.user:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json() or {}
    field = data.get("field")
    value = data.get("value")
    
    allowed_fields = [
        "stage", "proposals_sent", "responses_received", "interviews_held",
        "offers_received", "contracts_won", "is_actively_seeking"
    ]
    
    if field not in allowed_fields:
        return jsonify({"error": f"Invalid field: {field}"}), 400
    
    sb = get_supabase()
    update_data = {field: value, "updated_at": "now()"}
    
    if field == "stage" and value == "applying":
        update_data["started_learning_at"] = sb.table("freelance_pipeline")  # no-op, just stage update
    
    sb.table("freelance_pipeline").update(update_data) \
        .eq("user_id", g.user["id"]) \
        .execute()
    
    return jsonify({"success": True})


@freelance_bp.route("/contract/add", methods=["POST"])
def add_contract():
    """Add a new contract record."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    platform = request.form.get("platform", "")
    client_name = request.form.get("client_name", "").strip()
    project_title = request.form.get("project_title", "").strip()
    contract_value = request.form.get("contract_value", type=float, default=0)
    hours_worked = request.form.get("hours_worked", type=int, default=0)
    
    if not client_name or not project_title:
        flash("Client name and project title are required", "error")
        return redirect(url_for("freelance.pipeline"))
    
    # Find the pipeline for this topic
    pipeline_topic = request.form.get("topic", "")
    pipeline_resp = sb.table("freelance_pipeline").select("*") \
        .eq("user_id", user_id) \
        .eq("topic", pipeline_topic) \
        .limit(1) \
        .execute()
    
    pipeline_id = None
    if pipeline_resp.data:
        pipeline_id = pipeline_resp.data[0]["id"]
        
        # Update pipeline stats
        contracts_won = pipeline_resp.data[0].get("contracts_won", 0) + 1
        total_earned = (pipeline_resp.data[0].get("total_earned", 0) or 0) + contract_value
        
        sb.table("freelance_pipeline").update({
            "contracts_won": contracts_won,
            "total_earned": total_earned,
            "stage": "contracted",
            "updated_at": "now()"
        }).eq("id", pipeline_id).execute()
    
    # Insert contract
    sb.table("contracts").insert({
        "user_id": user_id,
        "pipeline_id": pipeline_id,
        "platform": platform,
        "client_name": client_name,
        "project_title": project_title,
        "contract_value": contract_value,
        "your_rate": contract_value / hours_worked if hours_worked > 0 else 0,
        "hours_worked": hours_worked,
        "start_date": date.today().isoformat(),
        "status": "active",
    }).execute()
    
    flash("Contract added! Track your earnings grow. 🎉", "success")
    return redirect(url_for("freelance.pipeline"))

from __future__ import annotations

from flask import Blueprint
from flask import render_template

bp = Blueprint("web", __name__)


@bp.get("/")
def dashboard():
    metrics = {
        "month_spending": "0.00",
        "total_spending": "0.00",
        "voucher_count": 0,
        "pending_count": 0,
        "expiring_qualifications": 0,
    }
    return render_template("dashboard.html", metrics=metrics)

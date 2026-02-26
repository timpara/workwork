import csv
import io
import json
from datetime import datetime, timedelta
from collections import defaultdict

from flask import Flask, render_template, request, jsonify, Response

from .database import get_db, get_setting, set_setting, init_db
from .models import (
    calculate_hours,
    entry_to_dict,
    validate_entry,
    DAILY_TARGET,
)

app = Flask(__name__)


@app.before_request
def ensure_db():
    """Ensure database is initialized on first request."""
    if not hasattr(app, "_db_initialized"):
        init_db()
        app._db_initialized = True


# ─── Pages ───────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


# ─── API: CRUD ───────────────────────────────────────────────────────────────


@app.get("/api/entries")
def list_entries():
    """List entries with optional year/month filter."""
    year = request.args.get("year")
    month = request.args.get("month")

    db = get_db()
    try:
        if year and month:
            prefix = f"{int(year):04d}-{int(month):02d}"
            rows = db.execute(
                "SELECT * FROM time_entries WHERE date LIKE ? ORDER BY date DESC",
                (f"{prefix}%",),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM time_entries ORDER BY date DESC"
            ).fetchall()

        entries = [entry_to_dict(r) for r in rows]
        return jsonify(entries)
    finally:
        db.close()


@app.post("/api/entries")
def create_entry():
    """Create a new time entry."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    valid, error = validate_entry(data)
    if not valid:
        return jsonify({"error": error}), 400

    breaks = data.get("breaks", [])
    daily_target = float(get_setting("daily_target", str(DAILY_TARGET)))
    total_hours, overtime = calculate_hours(
        data["start_time"], data["end_time"], breaks, daily_target
    )

    db = get_db()
    try:
        db.execute(
            """INSERT INTO time_entries (date, start_time, end_time, breaks, total_hours, overtime, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["date"],
                data["start_time"],
                data["end_time"],
                json.dumps(breaks),
                total_hours,
                overtime,
                data.get("note", ""),
            ),
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM time_entries WHERE date = ?", (data["date"],)
        ).fetchone()
        return jsonify(entry_to_dict(row)), 201
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            return jsonify(
                {"error": f"Entry for {data['date']} already exists. Edit it instead."}
            ), 409
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.put("/api/entries/<int:entry_id>")
def update_entry(entry_id):
    """Update an existing time entry."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    valid, error = validate_entry(data)
    if not valid:
        return jsonify({"error": error}), 400

    breaks = data.get("breaks", [])
    daily_target = float(get_setting("daily_target", str(DAILY_TARGET)))
    total_hours, overtime = calculate_hours(
        data["start_time"], data["end_time"], breaks, daily_target
    )

    db = get_db()
    try:
        result = db.execute(
            """UPDATE time_entries
               SET date=?, start_time=?, end_time=?, breaks=?, total_hours=?, overtime=?, note=?,
                   updated_at=datetime('now')
               WHERE id=?""",
            (
                data["date"],
                data["start_time"],
                data["end_time"],
                json.dumps(breaks),
                total_hours,
                overtime,
                data.get("note", ""),
                entry_id,
            ),
        )
        db.commit()
        if result.rowcount == 0:
            return jsonify({"error": "Entry not found"}), 404
        row = db.execute(
            "SELECT * FROM time_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return jsonify(entry_to_dict(row))
    finally:
        db.close()


@app.delete("/api/entries/<int:entry_id>")
def delete_entry(entry_id):
    """Delete a time entry."""
    db = get_db()
    try:
        result = db.execute("DELETE FROM time_entries WHERE id = ?", (entry_id,))
        db.commit()
        if result.rowcount == 0:
            return jsonify({"error": "Entry not found"}), 404
        return jsonify({"message": "Deleted"})
    finally:
        db.close()


# ─── API: Adjustments ────────────────────────────────────────────────────────


@app.get("/api/adjustments")
def list_adjustments():
    """List all manual overtime adjustments."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM adjustments ORDER BY created_at DESC"
        ).fetchall()
        return jsonify(
            [
                {
                    "id": r["id"],
                    "hours": r["hours"],
                    "reason": r["reason"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        )
    finally:
        db.close()


@app.post("/api/adjustments")
def create_adjustment():
    """Create a manual overtime adjustment."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    hours = data.get("hours")
    reason = data.get("reason", "").strip()

    if hours is None or not isinstance(hours, (int, float)):
        return jsonify({"error": "Hours must be a number"}), 400
    if not reason:
        return jsonify({"error": "Reason is required"}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO adjustments (hours, reason) VALUES (?, ?)",
            (float(hours), reason),
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM adjustments ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return jsonify(
            {
                "id": row["id"],
                "hours": row["hours"],
                "reason": row["reason"],
                "created_at": row["created_at"],
            }
        ), 201
    finally:
        db.close()


@app.delete("/api/adjustments/<int:adj_id>")
def delete_adjustment(adj_id):
    """Delete a manual overtime adjustment."""
    db = get_db()
    try:
        result = db.execute("DELETE FROM adjustments WHERE id = ?", (adj_id,))
        db.commit()
        if result.rowcount == 0:
            return jsonify({"error": "Adjustment not found"}), 404
        return jsonify({"message": "Deleted"})
    finally:
        db.close()


# ─── API: Settings ───────────────────────────────────────────────────────────


@app.get("/api/settings")
def get_settings():
    """Get application settings."""
    daily_target = float(get_setting("daily_target", str(DAILY_TARGET)))
    return jsonify({"daily_target": daily_target})


@app.put("/api/settings")
def update_settings():
    """Update application settings."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "daily_target" in data:
        val = data["daily_target"]
        if not isinstance(val, (int, float)) or val <= 0 or val > 24:
            return jsonify(
                {"error": "daily_target must be a number between 0 and 24"}
            ), 400
        set_setting("daily_target", str(float(val)))

    daily_target = float(get_setting("daily_target", str(DAILY_TARGET)))
    return jsonify({"daily_target": daily_target})


# ─── API: Summaries ─────────────────────────────────────────────────────────


@app.get("/api/summary/weekly")
def weekly_summary():
    """Get weekly summaries. Optional ?year=&month= filter."""
    year = request.args.get("year")
    month = request.args.get("month")

    db = get_db()
    try:
        if year and month:
            prefix = f"{int(year):04d}-{int(month):02d}"
            rows = db.execute(
                "SELECT * FROM time_entries WHERE date LIKE ? ORDER BY date",
                (f"{prefix}%",),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM time_entries ORDER BY date").fetchall()

        entries = [entry_to_dict(r) for r in rows]
        daily_target = float(get_setting("daily_target", str(DAILY_TARGET)))
        weeks = defaultdict(
            lambda: {"entries": [], "total_hours": 0, "target": 0, "overtime": 0}
        )

        for entry in entries:
            d = datetime.strptime(entry["date"], "%Y-%m-%d")
            # ISO week: year-Wxx
            iso_year, iso_week, _ = d.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"

            # Calculate Monday of this week for display
            monday = d - timedelta(days=d.weekday())
            sunday = monday + timedelta(days=6)

            weeks[week_key]["week"] = week_key
            weeks[week_key]["monday"] = monday.strftime("%Y-%m-%d")
            weeks[week_key]["sunday"] = sunday.strftime("%Y-%m-%d")
            weeks[week_key]["entries"].append(entry)
            weeks[week_key]["total_hours"] += entry["total_hours"]
            weeks[week_key]["target"] += daily_target

        # Compute overtime per week
        result = []
        for key in sorted(weeks.keys(), reverse=True):
            w = weeks[key]
            w["total_hours"] = round(w["total_hours"], 2)
            w["overtime"] = round(w["total_hours"] - w["target"], 2)
            w["days_worked"] = len(w["entries"])
            del w["entries"]  # Don't send full entries in summary
            result.append(w)

        return jsonify(result)
    finally:
        db.close()


@app.get("/api/summary/monthly")
def monthly_summary():
    """Get monthly summaries."""
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM time_entries ORDER BY date").fetchall()

        entries = [entry_to_dict(r) for r in rows]
        daily_target = float(get_setting("daily_target", str(DAILY_TARGET)))
        months = defaultdict(lambda: {"total_hours": 0, "target": 0, "days_worked": 0})

        for entry in entries:
            month_key = entry["date"][:7]  # YYYY-MM
            months[month_key]["month"] = month_key
            months[month_key]["total_hours"] += entry["total_hours"]
            months[month_key]["target"] += daily_target
            months[month_key]["days_worked"] += 1

        result = []
        for key in sorted(months.keys(), reverse=True):
            m = months[key]
            m["total_hours"] = round(m["total_hours"], 2)
            m["overtime"] = round(m["total_hours"] - m["target"], 2)
            result.append(m)

        return jsonify(result)
    finally:
        db.close()


@app.get("/api/summary/total")
def total_summary():
    """Get total cumulative overtime including manual adjustments."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT COALESCE(SUM(overtime), 0) as total_overtime, "
            "COALESCE(SUM(total_hours), 0) as total_hours, "
            "COUNT(*) as total_days "
            "FROM time_entries"
        ).fetchone()
        adj_row = db.execute(
            "SELECT COALESCE(SUM(hours), 0) as total_adj FROM adjustments"
        ).fetchone()
        manual_adj = round(adj_row["total_adj"], 2)
        entries_overtime = round(row["total_overtime"], 2)
        return jsonify(
            {
                "total_overtime": entries_overtime,
                "manual_adjustment": manual_adj,
                "combined_balance": round(entries_overtime + manual_adj, 2),
                "total_hours": round(row["total_hours"], 2),
                "total_days": row["total_days"],
                "daily_target": float(get_setting("daily_target", str(DAILY_TARGET))),
            }
        )
    finally:
        db.close()


# ─── API: Export ─────────────────────────────────────────────────────────────


@app.get("/api/export/csv")
def export_csv():
    """Export all entries and adjustments as CSV."""
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM time_entries ORDER BY date").fetchall()
        adj_rows = db.execute(
            "SELECT * FROM adjustments ORDER BY created_at"
        ).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Date",
                "Start Time",
                "End Time",
                "Breaks",
                "Total Hours",
                "Overtime",
                "Note",
            ]
        )

        for row in rows:
            breaks = json.loads(row["breaks"])
            breaks_str = (
                "; ".join(f"{b['start']}-{b['end']}" for b in breaks)
                if breaks
                else "None"
            )
            writer.writerow(
                [
                    row["date"],
                    row["start_time"],
                    row["end_time"],
                    breaks_str,
                    row["total_hours"],
                    row["overtime"],
                    row["note"] or "",
                ]
            )

        # Append manual adjustments
        for adj in adj_rows:
            writer.writerow(
                [
                    "ADJUSTMENT",
                    "",
                    "",
                    "",
                    "",
                    adj["hours"],
                    adj["reason"],
                ]
            )

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=work_hours_{datetime.now().strftime('%Y%m%d')}.csv"
            },
        )
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=9090, debug=True)

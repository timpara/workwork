"""Integration tests for the Flask API using a temporary database."""

import csv
import io
import json
import os
import tempfile

import pytest

# Set DB_PATH before importing app modules so init_db uses the temp file
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name

from app.app import app  # noqa: E402
from app.database import init_db  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    """Re-create the database for every test."""
    # Remove the old file and create a fresh one
    if os.path.exists(os.environ["DB_PATH"]):
        os.unlink(os.environ["DB_PATH"])
    # Reset the init flag so before_request will call init_db again
    if hasattr(app, "_db_initialized"):
        del app._db_initialized
    init_db()
    yield
    # cleanup
    if os.path.exists(os.environ["DB_PATH"]):
        os.unlink(os.environ["DB_PATH"])


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ─── Helpers ──────────────────────────────────────────────────────────────────

SAMPLE_ENTRY = {
    "date": "2025-06-10",
    "start_time": "08:00",
    "end_time": "16:06",
    "breaks": [{"start": "12:00", "end": "12:30"}],
    "note": "normal day",
}


def post_entry(client, data=None):
    """Helper to POST a time entry."""
    return client.post(
        "/api/entries",
        data=json.dumps(data or SAMPLE_ENTRY),
        content_type="application/json",
    )


def post_adjustment(client, hours=2.0, reason="On-call"):
    return client.post(
        "/api/adjustments",
        data=json.dumps({"hours": hours, "reason": reason}),
        content_type="application/json",
    )


# ─── Page ─────────────────────────────────────────────────────────────────────


def test_index_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Work Hours" in res.data


# ─── Entries CRUD ─────────────────────────────────────────────────────────────


def test_create_entry(client):
    res = post_entry(client)
    assert res.status_code == 201
    data = res.get_json()
    assert data["date"] == "2025-06-10"
    assert data["total_hours"] == 7.6
    assert data["overtime"] == 0.0


def test_create_entry_duplicate(client):
    post_entry(client)
    res = post_entry(client)
    assert res.status_code == 409
    assert "already exists" in res.get_json()["error"]


def test_create_entry_invalid(client):
    res = client.post(
        "/api/entries",
        data=json.dumps({"date": "2025-06-10"}),
        content_type="application/json",
    )
    assert res.status_code == 400


def test_list_entries(client):
    post_entry(client)
    res = client.get("/api/entries")
    assert res.status_code == 200
    entries = res.get_json()
    assert len(entries) == 1
    assert entries[0]["date"] == "2025-06-10"


def test_list_entries_filtered(client):
    post_entry(client)
    # Different month entry
    post_entry(client, {**SAMPLE_ENTRY, "date": "2025-07-01"})

    res = client.get("/api/entries?year=2025&month=6")
    entries = res.get_json()
    assert len(entries) == 1
    assert entries[0]["date"] == "2025-06-10"


def test_update_entry(client):
    res = post_entry(client)
    entry_id = res.get_json()["id"]

    updated = {**SAMPLE_ENTRY, "end_time": "17:06"}
    res = client.put(
        f"/api/entries/{entry_id}",
        data=json.dumps(updated),
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.get_json()["total_hours"] == 8.6
    assert res.get_json()["overtime"] == 1.0


def test_update_entry_not_found(client):
    res = client.put(
        "/api/entries/9999",
        data=json.dumps(SAMPLE_ENTRY),
        content_type="application/json",
    )
    assert res.status_code == 404


def test_delete_entry(client):
    res = post_entry(client)
    entry_id = res.get_json()["id"]
    res = client.delete(f"/api/entries/{entry_id}")
    assert res.status_code == 200

    # Confirm gone
    res = client.get("/api/entries")
    assert len(res.get_json()) == 0


def test_delete_entry_not_found(client):
    res = client.delete("/api/entries/9999")
    assert res.status_code == 404


# ─── Summaries ────────────────────────────────────────────────────────────────


def test_total_summary_empty(client):
    res = client.get("/api/summary/total")
    data = res.get_json()
    assert data["total_days"] == 0
    assert data["total_hours"] == 0
    assert data["combined_balance"] == 0


def test_total_summary_with_entries(client):
    post_entry(client)
    # Add a second entry with overtime
    post_entry(client, {**SAMPLE_ENTRY, "date": "2025-06-11", "end_time": "17:06"})

    res = client.get("/api/summary/total")
    data = res.get_json()
    assert data["total_days"] == 2
    assert data["total_hours"] == 7.6 + 8.6
    assert data["total_overtime"] == 0.0 + 1.0
    assert data["combined_balance"] == 1.0


def test_weekly_summary(client):
    post_entry(client)
    res = client.get("/api/summary/weekly?year=2025&month=6")
    weeks = res.get_json()
    assert len(weeks) >= 1
    assert weeks[0]["days_worked"] >= 1


def test_monthly_summary(client):
    post_entry(client)
    res = client.get("/api/summary/monthly")
    months = res.get_json()
    assert len(months) == 1
    assert months[0]["month"] == "2025-06"
    assert months[0]["days_worked"] == 1


def test_export_csv(client):
    post_entry(client)
    res = client.get("/api/export/csv")
    assert res.status_code == 200
    assert "text/csv" in res.content_type

    reader = csv.reader(io.StringIO(res.data.decode()))
    rows = list(reader)
    assert rows[0][0] == "Date"  # header
    assert rows[1][0] == "2025-06-10"


# ─── Adjustments ──────────────────────────────────────────────────────────────


def test_create_adjustment(client):
    res = post_adjustment(client, hours=3.5, reason="On-call weekend")
    assert res.status_code == 201
    data = res.get_json()
    assert data["hours"] == 3.5
    assert data["reason"] == "On-call weekend"


def test_create_adjustment_invalid(client):
    # Missing reason
    res = client.post(
        "/api/adjustments",
        data=json.dumps({"hours": 2.0, "reason": ""}),
        content_type="application/json",
    )
    assert res.status_code == 400

    # Missing hours
    res = client.post(
        "/api/adjustments",
        data=json.dumps({"reason": "test"}),
        content_type="application/json",
    )
    assert res.status_code == 400


def test_list_adjustments(client):
    post_adjustment(client, hours=2.0, reason="On-call")
    post_adjustment(client, hours=-1.0, reason="Left early")

    res = client.get("/api/adjustments")
    adjustments = res.get_json()
    assert len(adjustments) == 2


def test_delete_adjustment(client):
    res = post_adjustment(client)
    adj_id = res.get_json()["id"]

    res = client.delete(f"/api/adjustments/{adj_id}")
    assert res.status_code == 200

    res = client.get("/api/adjustments")
    assert len(res.get_json()) == 0


def test_total_summary_with_adjustment(client):
    """combined_balance = entries overtime + manual adjustments."""
    # Entry: 08:00-17:06, 30min break => 8.6h, OT = +1.0
    post_entry(client, {**SAMPLE_ENTRY, "end_time": "17:06"})
    # Adjustment: +2.5h
    post_adjustment(client, hours=2.5, reason="Initial balance")

    res = client.get("/api/summary/total")
    data = res.get_json()
    assert data["total_overtime"] == 1.0
    assert data["manual_adjustment"] == 2.5
    assert data["combined_balance"] == 3.5


def test_export_csv_with_adjustments(client):
    """CSV includes entry rows and ADJUSTMENT rows."""
    post_entry(client)
    post_adjustment(client, hours=5.0, reason="Comp time")

    res = client.get("/api/export/csv")
    reader = csv.reader(io.StringIO(res.data.decode()))
    rows = list(reader)

    # Header + 1 entry + 1 adjustment = 3 rows
    assert len(rows) == 3
    assert rows[1][0] == "2025-06-10"
    assert rows[2][0] == "ADJUSTMENT"
    assert rows[2][5] == "5.0"
    assert rows[2][6] == "Comp time"

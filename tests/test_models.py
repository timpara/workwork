"""Unit tests for app.models — pure calculation and validation logic."""

import pytest
from app.models import (
    calculate_hours,
    calculate_break_minutes,
    validate_entry,
    entry_to_dict,
    DAILY_TARGET,
)


# ─── calculate_hours ─────────────────────────────────────────────────────────


def test_calculate_hours_exact_target():
    """08:00-16:06 with 30min break = 7.6h, overtime = 0."""
    total, overtime = calculate_hours(
        "08:00", "16:06", [{"start": "12:00", "end": "12:30"}], daily_target=7.6
    )
    assert total == 7.6
    assert overtime == 0.0


def test_calculate_hours_overtime():
    """08:00-17:06 with 30min break = 8.6h, overtime = +1.0."""
    total, overtime = calculate_hours(
        "08:00", "17:06", [{"start": "12:00", "end": "12:30"}], daily_target=7.6
    )
    assert total == 8.6
    assert overtime == 1.0


def test_calculate_hours_undertime():
    """08:00-15:00 with 30min break = 6.5h, overtime = -1.1."""
    total, overtime = calculate_hours(
        "08:00", "15:00", [{"start": "12:00", "end": "12:30"}], daily_target=7.6
    )
    assert total == 6.5
    assert overtime == -1.1


def test_calculate_hours_no_breaks():
    """08:00-15:36 with no breaks = 7.6h, overtime = 0."""
    total, overtime = calculate_hours("08:00", "15:36", [], daily_target=7.6)
    assert total == 7.6
    assert overtime == 0.0


def test_calculate_hours_multiple_breaks():
    """08:00-16:21 with two breaks totaling 45min = 7.6h."""
    breaks = [
        {"start": "10:00", "end": "10:15"},
        {"start": "12:00", "end": "12:30"},
    ]
    total, overtime = calculate_hours("08:00", "16:21", breaks, daily_target=7.6)
    assert total == 7.6
    assert overtime == 0.0


def test_calculate_hours_overnight():
    """22:00-06:30 with 30min break = 8.0h (overnight shift)."""
    total, overtime = calculate_hours(
        "22:00", "06:30", [{"start": "02:00", "end": "02:30"}], daily_target=7.6
    )
    assert total == 8.0
    assert overtime == 0.4


def test_calculate_hours_custom_target():
    """With daily_target=8.0, 7.6h worked gives overtime = -0.4."""
    total, overtime = calculate_hours(
        "08:00", "16:06", [{"start": "12:00", "end": "12:30"}], daily_target=8.0
    )
    assert total == 7.6
    assert overtime == -0.4


# ─── calculate_break_minutes ─────────────────────────────────────────────────


def test_calculate_break_minutes():
    """Various break lists produce correct total minutes."""
    # Single 30-min break
    assert calculate_break_minutes([{"start": "12:00", "end": "12:30"}]) == 30.0

    # Two breaks
    breaks = [
        {"start": "10:00", "end": "10:15"},
        {"start": "12:00", "end": "12:30"},
    ]
    assert calculate_break_minutes(breaks) == 45.0

    # Empty list
    assert calculate_break_minutes([]) == 0.0


# ─── validate_entry ──────────────────────────────────────────────────────────


def test_validate_entry_valid():
    """A fully valid entry passes validation."""
    data = {
        "date": "2025-01-15",
        "start_time": "08:00",
        "end_time": "16:00",
        "breaks": [{"start": "12:00", "end": "12:30"}],
    }
    valid, error = validate_entry(data)
    assert valid is True
    assert error == ""


def test_validate_entry_missing_date():
    """Missing date field returns error."""
    data = {"start_time": "08:00", "end_time": "16:00"}
    valid, error = validate_entry(data)
    assert valid is False
    assert "Missing" in error


def test_validate_entry_invalid_time():
    """Invalid time format returns error."""
    data = {"date": "2025-01-15", "start_time": "8am", "end_time": "16:00"}
    valid, error = validate_entry(data)
    assert valid is False
    assert "Invalid time" in error


def test_validate_entry_invalid_break():
    """Break with missing fields returns error."""
    data = {
        "date": "2025-01-15",
        "start_time": "08:00",
        "end_time": "16:00",
        "breaks": [{"start": "12:00"}],
    }
    valid, error = validate_entry(data)
    assert valid is False
    assert "Break 1" in error


# ─── entry_to_dict ───────────────────────────────────────────────────────────


def test_entry_to_dict():
    """Convert a mock sqlite3.Row-like dict to the expected format."""

    class FakeRow:
        """Mimic sqlite3.Row with subscript access."""

        def __init__(self, data):
            self._data = data

        def __getitem__(self, key):
            return self._data[key]

    row = FakeRow(
        {
            "id": 1,
            "date": "2025-01-15",
            "start_time": "08:00",
            "end_time": "16:06",
            "breaks": '[{"start":"12:00","end":"12:30"}]',
            "total_hours": 7.6,
            "overtime": 0.0,
            "note": "test note",
            "created_at": "2025-01-15 10:00:00",
            "updated_at": "2025-01-15 10:00:00",
        }
    )

    d = entry_to_dict(row)
    assert d["id"] == 1
    assert d["date"] == "2025-01-15"
    assert d["breaks"] == [{"start": "12:00", "end": "12:30"}]
    assert d["total_hours"] == 7.6
    assert d["overtime"] == 0.0
    assert d["note"] == "test note"

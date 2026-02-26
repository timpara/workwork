import json
from datetime import datetime, timedelta

DAILY_TARGET = 7.6  # hours


def parse_time(time_str: str) -> datetime:
    """Parse a HH:MM time string into a datetime object (date doesn't matter)."""
    return datetime.strptime(time_str, "%H:%M")


def calculate_break_minutes(breaks: list[dict]) -> float:
    """Calculate total break duration in minutes from a list of break dicts."""
    total = 0.0
    for b in breaks:
        start = parse_time(b["start"])
        end = parse_time(b["end"])
        diff = (end - start).total_seconds() / 60.0
        if diff > 0:
            total += diff
    return total


def calculate_hours(
    start_time: str, end_time: str, breaks: list[dict]
) -> tuple[float, float]:
    """
    Calculate total worked hours and overtime.
    Returns (total_hours, overtime).
    """
    start = parse_time(start_time)
    end = parse_time(end_time)

    # Handle overnight shifts
    total_minutes = (end - start).total_seconds() / 60.0
    if total_minutes < 0:
        total_minutes += 24 * 60

    break_minutes = calculate_break_minutes(breaks)
    worked_minutes = total_minutes - break_minutes
    worked_hours = round(worked_minutes / 60.0, 2)
    overtime = round(worked_hours - DAILY_TARGET, 2)

    return max(worked_hours, 0), overtime


def entry_to_dict(row) -> dict:
    """Convert a database row to a dictionary."""
    return {
        "id": row["id"],
        "date": row["date"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "breaks": json.loads(row["breaks"]),
        "total_hours": row["total_hours"],
        "overtime": row["overtime"],
        "note": row["note"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def validate_entry(data: dict) -> tuple[bool, str]:
    """Validate a time entry. Returns (is_valid, error_message)."""
    required = ["date", "start_time", "end_time"]
    for field in required:
        if field not in data or not data[field]:
            return False, f"Missing required field: {field}"

    # Validate date format
    try:
        datetime.strptime(data["date"], "%Y-%m-%d")
    except ValueError:
        return False, "Invalid date format. Use YYYY-MM-DD."

    # Validate time format
    for field in ["start_time", "end_time"]:
        try:
            parse_time(data[field])
        except ValueError:
            return False, f"Invalid time format for {field}. Use HH:MM."

    # Validate breaks
    breaks = data.get("breaks", [])
    if not isinstance(breaks, list):
        return False, "Breaks must be a list."

    for i, b in enumerate(breaks):
        if "start" not in b or "end" not in b:
            return False, f"Break {i + 1} must have 'start' and 'end' fields."
        try:
            parse_time(b["start"])
            parse_time(b["end"])
        except ValueError:
            return False, f"Invalid time format in break {i + 1}. Use HH:MM."

    return True, ""

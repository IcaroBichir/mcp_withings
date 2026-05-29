from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .client import WithingsClient

mcp = FastMCP(
    "Withings",
    instructions=(
        "Use these tools to retrieve the authenticated user's Withings health data. "
        "Weight and mass values are in kg. Durations are in seconds. "
        "Distance is in meters. Always convert to human-readable units when presenting results."
    ),
)


def _parse_date_range(
    start: Optional[str], end: Optional[str], default_days: int = 30
) -> tuple[date, date]:
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = (
        date.fromisoformat(start) if start
        else end_date - timedelta(days=default_days - 1)
    )
    if start_date > end_date:
        raise ValueError(f"start_date ({start_date}) must be on or before end_date ({end_date})")
    delta = (end_date - start_date).days
    if delta > 364:
        raise ValueError("Date range cannot exceed 365 days")
    return start_date, end_date


@mcp.tool()
def get_measurements(
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> list[dict]:
    """
    Get body composition measurements from the Withings scale.

    Returns daily records with weight, fat ratio, fat mass, fat-free mass,
    muscle mass, bone mass, and hydration. Results are newest first.

    Fields (when available): weight_kg, fat_ratio_pct, fat_mass_kg,
    fat_free_mass_kg, muscle_mass_kg, bone_mass_kg, hydration_kg.

    Args:
        start: Start date ISO 8601 (e.g. "2026-01-01"). Defaults to 30 days ago.
        end: End date ISO 8601 (e.g. "2026-05-29"). Defaults to today.
    """
    start_date, end_date = _parse_date_range(start, end, default_days=30)
    return WithingsClient().get_measurements(start_date, end_date)


@mcp.tool()
def get_activity_summary(
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> list[dict]:
    """
    Get daily activity summaries from Withings trackers.

    Returns one record per day with step count, distance walked/run,
    active calories burned, total calories, active time broken down by
    intensity (soft/moderate/intense), and daily HR stats.

    Fields (when available): steps, distance (m), elevation (m),
    calories, totalcalories, active (s), soft (s), moderate (s),
    intense (s), hr_average, hr_min, hr_max.

    Args:
        start: Start date ISO 8601. Defaults to 7 days ago.
        end: End date ISO 8601. Defaults to today.
    """
    start_date, end_date = _parse_date_range(start, end, default_days=7)
    return WithingsClient().get_activity_summary(start_date, end_date)


@mcp.tool()
def get_workouts(
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> list[dict]:
    """
    Get recorded workout sessions from Withings devices.

    Returns each workout with sport type, start/end timestamps, duration,
    distance, calories burned, and heart rate stats.

    Fields (when available): date, sport, start, end, duration (s),
    distance (m), steps, calories, hr_average, hr_min, hr_max.

    Args:
        start: Start date ISO 8601. Defaults to 30 days ago.
        end: End date ISO 8601. Defaults to today.
    """
    start_date, end_date = _parse_date_range(start, end, default_days=30)
    return WithingsClient().get_workouts(start_date, end_date)


@mcp.tool()
def get_sleep_summary(
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> list[dict]:
    """
    Get nightly sleep summaries from the Withings sleep tracker or watch.

    Returns one record per night with sleep score, total sleep duration,
    time in bed, deep/light/REM stage durations, wake count, HR during
    sleep, and respiratory rate.

    Fields (when available): date, sleep_score, total_sleep_time (s),
    total_timeinbed (s), deepsleepduration (s), lightsleepduration (s),
    remsleepduration (s), wakeupcount, wakeupduration (s),
    durationtosleep (s), hr_average, hr_min, hr_max,
    rr_average, rr_min, rr_max, snoring (s), nb_remepidoses.

    Args:
        start: Start date ISO 8601. Defaults to 7 days ago.
        end: End date ISO 8601. Defaults to today.
    """
    start_date, end_date = _parse_date_range(start, end, default_days=7)
    return WithingsClient().get_sleep_summary(start_date, end_date)

"""Tests for the 4 MCP tool functions in withings_mcp.server.

WithingsClient is mocked — no live Withings auth needed.
"""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock, patch


@pytest.fixture()
def mock_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("withings_mcp.server.WithingsClient", lambda: client)
    return client


# ---------------------------------------------------------------------------
# get_measurements
# ---------------------------------------------------------------------------

class TestGetMeasurements:
    def test_returns_list(self, mock_client):
        from withings_mcp.server import get_measurements

        mock_client.get_measurements.return_value = [
            {"date": "2026-05-29", "weight_kg": 80.0, "fat_ratio_pct": 15.0}
        ]
        result = get_measurements("2026-05-01", "2026-05-29")
        assert isinstance(result, list)
        assert result[0]["weight_kg"] == 80.0

    def test_default_range_uses_30_days(self, mock_client):
        from withings_mcp.server import get_measurements

        mock_client.get_measurements.return_value = []
        get_measurements()
        call_args = mock_client.get_measurements.call_args[0]
        start, end = call_args
        assert (end - start).days == 29

    def test_reversed_dates_raises(self, mock_client):
        from withings_mcp.server import get_measurements

        with pytest.raises(ValueError):
            get_measurements("2026-05-29", "2026-05-01")

    def test_range_over_365_days_raises(self, mock_client):
        from withings_mcp.server import get_measurements

        with pytest.raises(ValueError, match="365"):
            get_measurements("2025-01-01", "2026-05-29")


# ---------------------------------------------------------------------------
# get_activity_summary
# ---------------------------------------------------------------------------

class TestGetActivitySummary:
    def test_returns_list(self, mock_client):
        from withings_mcp.server import get_activity_summary

        mock_client.get_activity_summary.return_value = [
            {"date": "2026-05-29", "steps": 8000, "calories": 2200.0}
        ]
        result = get_activity_summary("2026-05-23", "2026-05-29")
        assert isinstance(result, list)
        assert result[0]["steps"] == 8000

    def test_default_range_uses_7_days(self, mock_client):
        from withings_mcp.server import get_activity_summary

        mock_client.get_activity_summary.return_value = []
        get_activity_summary()
        call_args = mock_client.get_activity_summary.call_args[0]
        start, end = call_args
        assert (end - start).days == 6

    def test_reversed_dates_raises(self, mock_client):
        from withings_mcp.server import get_activity_summary

        with pytest.raises(ValueError):
            get_activity_summary("2026-05-29", "2026-05-01")


# ---------------------------------------------------------------------------
# get_workouts
# ---------------------------------------------------------------------------

class TestGetWorkouts:
    def test_returns_list(self, mock_client):
        from withings_mcp.server import get_workouts

        mock_client.get_workouts.return_value = [
            {
                "date": "2026-05-29",
                "sport": "Run",
                "duration": 3600,
                "calories": 400,
                "hr_average": 145,
            }
        ]
        result = get_workouts("2026-05-01", "2026-05-29")
        assert result[0]["sport"] == "Run"
        assert result[0]["duration"] == 3600

    def test_default_range_uses_30_days(self, mock_client):
        from withings_mcp.server import get_workouts

        mock_client.get_workouts.return_value = []
        get_workouts()
        call_args = mock_client.get_workouts.call_args[0]
        start, end = call_args
        assert (end - start).days == 29

    def test_reversed_dates_raises(self, mock_client):
        from withings_mcp.server import get_workouts

        with pytest.raises(ValueError):
            get_workouts("2026-05-29", "2026-05-01")


# ---------------------------------------------------------------------------
# get_sleep_summary
# ---------------------------------------------------------------------------

class TestGetSleepSummary:
    def test_returns_list(self, mock_client):
        from withings_mcp.server import get_sleep_summary

        mock_client.get_sleep_summary.return_value = [
            {
                "date": "2026-05-29",
                "sleep_score": 85,
                "total_sleep_time": 25200,
                "deepsleepduration": 5400,
            }
        ]
        result = get_sleep_summary("2026-05-23", "2026-05-29")
        assert result[0]["sleep_score"] == 85
        assert result[0]["total_sleep_time"] == 25200

    def test_default_range_uses_7_days(self, mock_client):
        from withings_mcp.server import get_sleep_summary

        mock_client.get_sleep_summary.return_value = []
        get_sleep_summary()
        call_args = mock_client.get_sleep_summary.call_args[0]
        start, end = call_args
        assert (end - start).days == 6

    def test_reversed_dates_raises(self, mock_client):
        from withings_mcp.server import get_sleep_summary

        with pytest.raises(ValueError):
            get_sleep_summary("2026-05-29", "2026-05-01")

    def test_empty_results_ok(self, mock_client):
        from withings_mcp.server import get_sleep_summary

        mock_client.get_sleep_summary.return_value = []
        result = get_sleep_summary("2026-05-01", "2026-05-07")
        assert result == []


# ---------------------------------------------------------------------------
# _parse_date_range (shared helper)
# ---------------------------------------------------------------------------

class TestParseDateRange:
    def test_explicit_range(self, mock_client):
        from withings_mcp.server import _parse_date_range

        start, end = _parse_date_range("2026-05-01", "2026-05-29")
        assert start == date(2026, 5, 1)
        assert end == date(2026, 5, 29)

    def test_no_args_defaults_to_n_days(self, mock_client):
        from withings_mcp.server import _parse_date_range

        start, end = _parse_date_range(None, None, default_days=7)
        assert end == date.today()
        assert (end - start).days == 6

    def test_start_only_uses_default_end_today(self, mock_client):
        from withings_mcp.server import _parse_date_range

        start, end = _parse_date_range("2026-05-01", None)
        assert end == date.today()
        assert start == date(2026, 5, 1)

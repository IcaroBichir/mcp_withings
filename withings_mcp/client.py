from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import httpx

from .auth import refresh_if_needed
from .cache import CacheStore

_BASE = "https://wbsapi.withings.net"

_TTL_MEASUREMENTS = 24 * 3600      # 24h — scale data doesn't change frequently
_TTL_ACTIVITY_HIST = 24 * 3600     # 24h — past days are immutable
_TTL_ACTIVITY_TODAY = 15 * 60      # 15min — today's data may update
_TTL_SLEEP_HIST = 24 * 3600
_TTL_SLEEP_TODAY = 15 * 60
_TTL_WORKOUTS_HIST = 24 * 3600
_TTL_WORKOUTS_TODAY = 15 * 60

# Body measurement type IDs → field names
_MEAS_TYPE_NAMES = {
    1: "weight_kg",
    5: "fat_free_mass_kg",
    6: "fat_ratio_pct",
    8: "fat_mass_kg",
    76: "muscle_mass_kg",
    77: "hydration_kg",
    88: "bone_mass_kg",
}
_BODY_MEASTYPES = ",".join(str(k) for k in _MEAS_TYPE_NAMES)

_WORKOUT_CATEGORIES = {
    1: "Walk", 2: "Run", 3: "Hiking", 4: "Skating", 6: "Biking",
    7: "Swimming", 16: "Weight Training", 17: "Golf", 18: "Yoga",
    19: "Dancing", 20: "Boxing", 24: "Ski", 25: "Snowboard",
    34: "Rowing", 36: "Pilates", 37: "Stepper", 38: "CrossFit",
    39: "Arc Trainer", 40: "Elliptical", 41: "Treadmill",
    306: "Weight Training", 307: "Cardio Training",
}

_ACTIVITY_FIELDS = (
    "steps,distance,elevation,soft,moderate,intense,active,"
    "calories,totalcalories,hr_average,hr_min,hr_max"
)
_WORKOUT_FIELDS = (
    "steps,distance,duration,calories,"
    "hr_average,hr_min,hr_max,hr_zone_0,hr_zone_1,hr_zone_2,hr_zone_3"
)
_SLEEP_FIELDS = (
    "deepsleepduration,durationtosleep,durationtowakeup,"
    "hr_average,hr_max,hr_min,lightsleepduration,nb_remepidoses,"
    "remsleepduration,rr_average,rr_max,rr_min,sleep_score,snoring,"
    "total_sleep_time,total_timeinbed,wakeupcount,wakeupduration"
)


def _apply_unit(value: int, unit: int) -> float:
    return round(value * (10 ** unit), 4)


def _to_ts(d: date, end_of_day: bool = False) -> int:
    if end_of_day:
        return int(datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc).timestamp())
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


class WithingsClient:
    def __init__(self) -> None:
        tokens = refresh_if_needed()
        self._token = tokens["access_token"]
        self._cache = CacheStore()

    def _get(self, path: str, **params: Any) -> dict:
        resp = httpx.get(
            f"{_BASE}{path}",
            headers={"Authorization": f"Bearer {self._token}"},
            params={k: v for k, v in params.items() if v is not None},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != 0:
            raise RuntimeError(
                f"Withings API error {data.get('status')}: {data.get('error', data)}"
            )
        return data.get("body", {})

    def _cached_get(self, key: str, path: str, ttl: int, **params: Any) -> dict:
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._get(path, **params)
        self._cache.set(key, result, ttl)
        return result

    def get_measurements(self, start_date: date, end_date: date) -> list[dict]:
        """Body composition measurements grouped by date, newest first."""
        cache_key = f"measurements:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        body = self._get(
            "/measure",
            action="getmeas",
            meastype=_BODY_MEASTYPES,
            category=1,
            startdate=_to_ts(start_date),
            enddate=_to_ts(end_date, end_of_day=True),
        )

        # Merge multiple measurement groups per day into one record
        by_date: dict[str, dict] = {}
        for grp in body.get("measuregrps", []):
            d = datetime.fromtimestamp(grp["date"], tz=timezone.utc).date().isoformat()
            if d not in by_date:
                by_date[d] = {"date": d}
            for m in grp.get("measures", []):
                name = _MEAS_TYPE_NAMES.get(m["type"])
                if name:
                    by_date[d][name] = _apply_unit(m["value"], m["unit"])

        result = sorted(by_date.values(), key=lambda x: x["date"], reverse=True)
        self._cache.set(cache_key, result, _TTL_MEASUREMENTS)
        return result

    def get_activity_summary(self, start_date: date, end_date: date) -> list[dict]:
        """Daily activity totals (steps, calories, distance, HR) for a date range."""
        today = date.today()
        cache_key = f"activity:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        body = self._get(
            "/v2/activity",
            action="getactivity",
            startdateymd=start_date.isoformat(),
            enddateymd=end_date.isoformat(),
            data_fields=_ACTIVITY_FIELDS,
        )

        result = []
        for a in sorted(body.get("activities", []), key=lambda x: x.get("date", ""), reverse=True):
            entry: dict = {"date": a["date"]}
            for field in (
                "steps", "distance", "elevation", "calories", "totalcalories",
                "active", "soft", "moderate", "intense",
                "hr_average", "hr_min", "hr_max",
            ):
                if a.get(field) is not None:
                    entry[field] = a[field]
            result.append(entry)

        ttl = _TTL_ACTIVITY_TODAY if end_date >= today else _TTL_ACTIVITY_HIST
        self._cache.set(cache_key, result, ttl)
        return result

    def get_workouts(self, start_date: date, end_date: date) -> list[dict]:
        """Workout sessions with sport type, duration, HR, and calories."""
        today = date.today()
        cache_key = f"workouts:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        body = self._get(
            "/v2/activity",
            action="getworkouts",
            startdateymd=start_date.isoformat(),
            enddateymd=end_date.isoformat(),
            data_fields=_WORKOUT_FIELDS,
        )

        result = []
        for w in sorted(body.get("series", []), key=lambda x: x.get("startdate", 0), reverse=True):
            category = w.get("category")
            sport = _WORKOUT_CATEGORIES.get(category, f"Activity({category})")
            entry: dict = {
                "date": w.get("date"),
                "sport": sport,
            }
            if "startdate" in w:
                entry["start"] = datetime.fromtimestamp(w["startdate"], tz=timezone.utc).isoformat()
            if "enddate" in w:
                entry["end"] = datetime.fromtimestamp(w["enddate"], tz=timezone.utc).isoformat()
            data = w.get("data", {})
            for field in ("steps", "distance", "duration", "calories",
                          "hr_average", "hr_min", "hr_max"):
                if data.get(field) is not None:
                    entry[field] = data[field]
            result.append({k: v for k, v in entry.items() if v is not None})

        ttl = _TTL_WORKOUTS_TODAY if end_date >= today else _TTL_WORKOUTS_HIST
        self._cache.set(cache_key, result, ttl)
        return result

    def get_sleep_summary(self, start_date: date, end_date: date) -> list[dict]:
        """Sleep summaries with stages, score, HR, and respiratory rate."""
        today = date.today()
        cache_key = f"sleep:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        body = self._get(
            "/v2/sleep",
            action="getsummary",
            startdateymd=start_date.isoformat(),
            enddateymd=end_date.isoformat(),
            data_fields=_SLEEP_FIELDS,
        )

        result = []
        for s in sorted(body.get("series", []), key=lambda x: x.get("date", ""), reverse=True):
            data = s.get("data", {})
            entry: dict = {"date": s["date"]}
            for field in (
                "sleep_score", "total_sleep_time", "total_timeinbed",
                "deepsleepduration", "lightsleepduration", "remsleepduration",
                "wakeupcount", "wakeupduration", "durationtosleep",
                "hr_average", "hr_min", "hr_max",
                "rr_average", "rr_min", "rr_max",
                "snoring", "nb_remepidoses",
            ):
                if data.get(field) is not None:
                    entry[field] = data[field]
            result.append(entry)

        ttl = _TTL_SLEEP_TODAY if end_date >= today else _TTL_SLEEP_HIST
        self._cache.set(cache_key, result, ttl)
        return result

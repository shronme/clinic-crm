from datetime import date, datetime, timedelta, time, timezone
from functools import lru_cache
from typing import Optional

import holidays
from zoneinfo import ZoneInfo


class HolidayService:
    """Service to determine if a given date is a holiday in Israel.

    Uses the `holidays` library which includes Israel holidays under
    country code "IL".
    """

    @staticmethod
    @lru_cache(maxsize=8)
    def _il_holidays(year: int) -> holidays.HolidayBase:
        return holidays.country_holidays("IL", years=year)

    @classmethod
    def is_holiday(cls, dt: datetime) -> bool:
        d: date = dt.date() if isinstance(dt, datetime) else dt  # type: ignore
        cal = cls._il_holidays(d.year)
        return d in cal

    @classmethod
    def get_holiday_name(cls, dt: datetime) -> Optional[str]:
        d: date = dt.date() if isinstance(dt, datetime) else dt  # type: ignore
        cal = cls._il_holidays(d.year)
        return cal.get(d)

    @classmethod
    def is_day_before_holiday(cls, dt: datetime) -> bool:
        """Return True if the given date is the day before a holiday in Israel.

        This is used to apply special operating rules on holiday eves.
        """
        d: date = dt.date() if isinstance(dt, datetime) else dt  # type: ignore
        next_day = d + timedelta(days=1)
        cal = cls._il_holidays(next_day.year)
        return next_day in cal

    @classmethod
    def get_pre_holiday_cutoff_utc(cls, dt: datetime) -> Optional[datetime]:
        """Return UTC time for 15:00 Asia/Jerusalem if this date is a
        holiday eve.

        If the given datetime's local date in Asia/Jerusalem is the day before
        a holiday, compute 15:00 local time and convert to UTC for comparison.
        """
        try:
            israel_tz = ZoneInfo("Asia/Jerusalem")
        except Exception:
            return None

        local_dt = dt.astimezone(israel_tz)
        local_date = local_dt.date()

        # Check if this local date is holiday eve
        if not cls.is_day_before_holiday(local_dt):
            return None

        cutoff_local = datetime.combine(local_date, time(15, 0), tzinfo=israel_tz)
        return cutoff_local.astimezone(timezone.utc)

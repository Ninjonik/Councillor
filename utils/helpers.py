"""
Helper utilities for common operations
"""
from datetime import datetime, timezone, timedelta
from typing import Optional


def datetime_now() -> datetime:
    """Get current datetime in UTC"""
    return datetime.now(timezone.utc)


def convert_datetime_from_str(datetime_str: str) -> Optional[datetime]:
    """
    Convert a datetime string to a datetime object

    Supported formats:
    - DD.MM.YYYY HH:MM
    - DD-MM-YYYY HH:MM
    - DD/MM/YYYY HH:MM

    Args:
        datetime_str: String to convert

    Returns:
        Datetime object in UTC or None if invalid
    """
    formats = ["%d.%m.%Y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"]

    for fmt in formats:
        try:
            datetime_obj = datetime.strptime(datetime_str, fmt)
            datetime_obj = datetime_obj.replace(tzinfo=timezone.utc)
            return datetime_obj
        except ValueError:
            continue

    return None


def calculate_voting_end_date(voting_days: int, after_noon: bool = False) -> datetime:
    """
    Calculate the end date for a voting period

    Args:
        voting_days: Number of days for voting
        after_noon: Whether to add an extra day if after noon

    Returns:
        Datetime for voting end (midnight UTC)
    """
    current_date = datetime_now()

    # If after noon, add one more day
    if after_noon and current_date.hour >= 12:
        days_to_add = voting_days + 1
    else:
        days_to_add = voting_days

    next_day = current_date + timedelta(days=days_to_add)

    # Set to midnight UTC (00:00:01)
    return datetime(next_day.year, next_day.month, next_day.day, 0, 0, 1, tzinfo=timezone.utc)


def generate_keycap_emoji(number: int) -> str:
    """Generate a keycap emoji for a number (1-9)"""
    keycap_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
    if 1 <= number <= 9:
        return keycap_emojis[number - 1]
    return str(number)


def seconds_until(hours: int, minutes: int) -> float:
    """
    Calculate seconds until a specific time today (or tomorrow if passed)

    Args:
        hours: Hour (0-23)
        minutes: Minute (0-59)

    Returns:
        Seconds until that time
    """
    from datetime import time

    given_time = time(hours, minutes)
    now = datetime_now()

    # Create datetime for today at given time
    future_exec = datetime.combine(now.date(), given_time, tzinfo=timezone.utc)

    # If we've passed that time today, schedule for tomorrow
    if future_exec < now:
        future_exec += timedelta(days=1)

    return (future_exec - now).total_seconds()


def truncate_for_embed(text: str, max_length: int = 1024) -> str:
    """
    Truncate text to fit in an embed field

    Args:
        text: Text to truncate
        max_length: Maximum length (default: 1024 for embed fields)

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to a human-readable string

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2d 5h 30m")
    """
    if seconds < 60:
        return f"{int(seconds)}s"

    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)}m"

    hours = minutes / 60
    if hours < 24:
        h = int(hours)
        m = int((hours - h) * 60)
        return f"{h}h {m}m"

    days = hours / 24
    d = int(days)
    h = int((days - d) * 24)
    return f"{d}d {h}h"


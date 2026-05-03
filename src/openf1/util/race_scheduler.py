"""Race window scheduler: checks if current time is within 12h before/after any race meeting."""
import logging
from datetime import datetime, timedelta, timezone

from openf1.util.db import _get_mongo_db_sync

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC for safe arithmetic."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_race_window(hours_before: int = 12, hours_after: int = 12) -> bool:
    """
    Check if current time is within a race window.
    
    Returns True if:
    - Current time is >= (meeting_date_start - hours_before)
    - AND <= (meeting_date_end + hours_after)
    
    Args:
        hours_before: hours before meeting start to consider active
        hours_after: hours after meeting end to consider active
    
    Returns:
        True if in any race window, False otherwise
    """
    try:
        now = _utc_now()
        db = _get_mongo_db_sync()
        meetings = db.get_collection("meetings")
        
        # Find all meetings within the window
        earliest_start = now - timedelta(hours=hours_before)
        latest_end = now + timedelta(hours=hours_after)
        
        # Query: meetings where date_start <= latest_end AND date_end >= earliest_start
        meeting = meetings.find_one({
            "date_start": {"$lte": latest_end},
            "date_end": {"$gte": earliest_start},
            "is_cancelled": {"$ne": True}  # Exclude cancelled meetings
        })
        
        if meeting:
            meeting_name = meeting.get('name', 'Unknown')
            meeting_start = _as_utc(meeting['date_start'])
            meeting_end = _as_utc(meeting['date_end'])
            window_end = meeting_end + timedelta(hours=hours_after)
            
            time_until_end = (window_end - now).total_seconds() / 3600
            
            logger.info(f"✓ IN RACE WINDOW: {meeting_name}")
            logger.info(f"  Meeting: {meeting_start} to {meeting_end}")
            logger.info(f"  Window end (+ {hours_after}h): {window_end} UTC")
            logger.info(f"  Stopping in: {time_until_end:.1f} hours")
            return True
        
        # Find next meeting for logging
        next_meeting = meetings.find_one(
            {"date_start": {"$gt": now}},
            sort=[("date_start", 1)]
        )
        
        if next_meeting:
            next_name = next_meeting.get('name', 'Unknown')
            next_start = _as_utc(next_meeting['date_start'])
            next_end = _as_utc(next_meeting['date_end'])
            window_start = next_start - timedelta(hours=hours_before)
            
            hours_until_start = (window_start - now).total_seconds() / 3600
            
            logger.info(f"✗ NOT IN RACE WINDOW")
            logger.info(f"  Next: {next_name}")
            logger.info(f"  Meeting: {next_start} to {next_end}")
            logger.info(f"  Window start (- {hours_before}h): {window_start} UTC")
            logger.info(f"  Starting in: {hours_until_start:.1f} hours")
        else:
            logger.info("✗ NOT IN RACE WINDOW")
            logger.info("  No upcoming meetings found")
        
        return False
    
    except Exception as exc:
        logger.warning(f"Error checking race window (will assume in-window): {exc}")
        # On error, assume we should run to avoid downtime surprises
        return True


def get_next_race_window(hours_before: int = 12, hours_after: int = 12) -> tuple[datetime, datetime] | None:
    """
    Get the start and end times of the next race window.
    
    Returns:
        Tuple of (window_start, window_end) or None if no meeting found
    """
    try:
        now = _utc_now()
        db = _get_mongo_db_sync()
        meetings = db.get_collection("meetings")
        
        next_meeting = meetings.find_one(
            {"date_start": {"$gt": now}},
            sort=[("date_start", 1)]
        )
        
        if next_meeting:
            next_start = _as_utc(next_meeting["date_start"])
            next_end = _as_utc(next_meeting["date_end"])
            window_start = next_start - timedelta(hours=hours_before)
            window_end = next_end + timedelta(hours=hours_after)
            
            hours_until_start = (window_start - now).total_seconds() / 3600
            meeting_name = next_meeting.get('name', 'Unknown')
            
            logger.debug(
                f"Next race window: {meeting_name} "
                f"starts at {window_start} UTC ({hours_until_start:.1f}h from now)"
            )
            return (window_start, window_end)
        
        return None
    except Exception as exc:
        logger.warning(f"Error getting next race window: {exc}")
        return None

"""Race window scheduler: checks if current time is within 12h before/after any race meeting."""
import logging
from datetime import datetime, timedelta
from typing import List

from openf1.util.db import _get_mongo_db_sync

logger = logging.getLogger(__name__)


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
        now = datetime.utcnow()
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
            logger.info(
                f"In race window for meeting: {meeting.get('name', 'Unknown')} "
                f"(starts {meeting['date_start']}, ends {meeting['date_end']})"
            )
            return True
        
        # Find next meeting for logging
        next_meeting = meetings.find_one(
            {"date_start": {"$gt": now}},
            sort=[("date_start", 1)]
        )
        
        if next_meeting:
            hours_until = (next_meeting["date_start"] - now).total_seconds() / 3600
            logger.info(
                f"Not in race window. Next meeting: {next_meeting.get('name', 'Unknown')} "
                f"in {hours_until:.1f} hours (at {next_meeting['date_start']})"
            )
        else:
            logger.info("Not in race window. No upcoming meetings found.")
        
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
        now = datetime.utcnow()
        db = _get_mongo_db_sync()
        meetings = db.get_collection("meetings")
        
        next_meeting = meetings.find_one(
            {"date_start": {"$gt": now}},
            sort=[("date_start", 1)]
        )
        
        if next_meeting:
            window_start = next_meeting["date_start"] - timedelta(hours=hours_before)
            window_end = next_meeting["date_end"] + timedelta(hours=hours_after)
            return (window_start, window_end)
        
        return None
    except Exception as exc:
        logger.warning(f"Error getting next race window: {exc}")
        return None

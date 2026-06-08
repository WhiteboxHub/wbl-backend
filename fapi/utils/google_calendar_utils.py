"""
Google Calendar Sync Utility
Automatically creates/updates/deletes Google Calendar events when interview
records are saved in the website.
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# NOTE: These are read inside functions so they always pick up the latest env values
DEFAULT_CALENDAR_ID = "sampath.velupula@gmail.com"
DEFAULT_CREDENTIALS_PATH = "fapi/google_calendar_credentials.json"


def _log(level: str, message: str):
    """Prints a clearly visible log line AND sends to Python logger."""
    icons = {"INFO": "✅", "WARN": "⚠️ ", "ERROR": "❌"}
    icon = icons.get(level, "ℹ️ ")
    full_msg = f"{icon} [Google Calendar] {message}"
    print(full_msg, flush=True)
    if level == "ERROR":
        logger.error(full_msg)
    else:
        logger.info(full_msg)


def _get_calendar_service():
    """
    Build and return an authenticated Google Calendar API service object.
    Reads env vars fresh every call so restarts are not needed for .env changes.
    Checks GOOGLE_CREDENTIALS_JSON env var first, then falls back to the local file.
    """
    # Read env vars fresh every time (avoids module-load-time caching issues)
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", DEFAULT_CREDENTIALS_PATH)

    try:
        scopes = ["https://www.googleapis.com/auth/calendar"]

        # 1. Try to load from environment variable string first
        if creds_json_str:
            try:
                # Strip surrounding single-quotes added by our .env format
                clean = creds_json_str.strip()
                if clean.startswith("'") and clean.endswith("'"):
                    clean = clean[1:-1]
                info = json.loads(clean)
                credentials = service_account.Credentials.from_service_account_info(
                    info, scopes=scopes
                )
                _log("INFO", "Google service built using GOOGLE_CREDENTIALS_JSON env var.")
                return build("calendar", "v3", credentials=credentials)
            except Exception as e:
                _log("WARN", f"GOOGLE_CREDENTIALS_JSON found but failed to parse: {e}")

        # 2. Fallback: local credentials file
        if os.path.exists(creds_path):
            credentials = service_account.Credentials.from_service_account_file(
                creds_path, scopes=scopes
            )
            _log("INFO", f"Google service built using file: {creds_path}")
            return build("calendar", "v3", credentials=credentials)

        _log("ERROR", f"No credentials found. Set GOOGLE_CREDENTIALS_JSON in .env or place file at '{creds_path}'.")
        return None

    except Exception as e:
        _log("ERROR", f"Failed to build Google Calendar service: {e}")
        return None


def _build_event_body(interview_data: dict, candidate_name: str) -> dict:
    """
    Builds the Google Calendar event dictionary from interview data.
    Creates a timed event if interview_time is present, otherwise an all-day event.
    """
    interview_date = interview_data.get("interview_date")
    interview_time = interview_data.get("interview_time")

    # Format title and description
    interview_type = interview_data.get("type_of_interview", "Interview")
    mode = interview_data.get("mode_of_interview", "")
    company = interview_data.get("company", "Unknown Company")
    notes = interview_data.get("notes", "")
    interviewer_emails = interview_data.get("interviewer_emails", "")
    feedback = interview_data.get("feedback", "Pending")

    title = f"[{interview_type}] {candidate_name} @ {company}"
    description_parts = [
        f"Candidate: {candidate_name}",
        f"Company: {company}",
        f"Interview Type: {interview_type}",
        f"Mode: {mode}" if mode else "",
        f"Interviewer Email(s): {interviewer_emails}" if interviewer_emails else "",
        f"Feedback: {feedback}",
        f"Notes: {notes}" if notes else "",
        "",
        "— Auto-synced from whitebox-learning.com",
    ]
    description = "\n".join([p for p in description_parts if p is not None])

    # Case 1: Timed Event
    if interview_time is not None and interview_time != "":
        # Convert time to string if it's a time object
        time_str = interview_time.strftime("%H:%M:%S") if hasattr(interview_time, "strftime") else str(interview_time)
        date_str = interview_date.isoformat() if hasattr(interview_date, "isoformat") else str(interview_date)
        
        start_datetime_str = f"{date_str}T{time_str}"
        # Start datetime object to calculate end time
        start_dt = datetime.fromisoformat(start_datetime_str)
        duration_minutes = int(interview_data.get("duration_minutes") or 60)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        return {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": os.getenv("GOOGLE_TIMEZONE", "America/Los_Angeles"),
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": os.getenv("GOOGLE_TIMEZONE", "America/Los_Angeles"),
            },
            "colorId": "1",
        }

    # Case 2: All-Day Event (Fallback)
    if hasattr(interview_date, "isoformat"):
        date_str = interview_date.isoformat()
    else:
        date_str = str(interview_date)

    try:
        end_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        end_date = date_str

    return {
        "summary": title,
        "description": description,
        "start": {"date": date_str},
        "end": {"date": end_date},
        "colorId": "1",
    }


def create_calendar_event(interview_data: dict, candidate_name: str) -> Optional[str]:  # noqa: E501
    """
    Creates a new Google Calendar event for an interview.
    Returns the event ID (stored in DB) or None if it fails.
    Only runs in production (APP_ENV=production).
    """
    app_env = os.getenv("APP_ENV", "local").strip().lower()
    if app_env != "production":
        _log("INFO", f"Skipping calendar CREATE — APP_ENV='{app_env}' (not production)")
        return None

    company = interview_data.get("company", "Unknown")
    date = interview_data.get("interview_date", "Unknown date")
    _log("INFO", f"Attempting to create event: '{candidate_name} @ {company}' on {date} ...")

    service = _get_calendar_service()
    if not service:
        return None

    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", DEFAULT_CALENDAR_ID)
    try:
        event_body = _build_event_body(interview_data, candidate_name)
        _log("INFO", f"DEBUG: Sending event body to Google: {event_body}")
        event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        event_id = event.get("id")
        event_link = event.get("htmlLink", "")
        _log("INFO", f"Event CREATED successfully!")
        _log("INFO", f"  → Event ID  : {event_id}")
        _log("INFO", f"  → Title     : {event_body['summary']}")
        _log("INFO", f"  → Date      : {date}")
        _log("INFO", f"  → Calendar  : {calendar_id}")
        _log("INFO", f"  → View it   : {event_link}")
        return event_id
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        _log("ERROR", f"Failed to create event for '{candidate_name} @ {company}': {e}\nFull Traceback:\n{error_details}")
        return None


def update_calendar_event(event_id: str, interview_data: dict, candidate_name: str) -> bool:
    """
    Updates an existing Google Calendar event.
    Returns True on success, False on failure.
    Only runs in production (APP_ENV=production).
    """
    app_env = os.getenv("APP_ENV", "local").strip().lower()
    if app_env != "production":
        _log("INFO", f"Skipping calendar UPDATE — APP_ENV='{app_env}' (not production)")
        return False

    if not event_id:
        _log("WARN", "Update skipped — no gcal_event_id stored for this interview")
        return False

    company = interview_data.get("company", "Unknown")
    _log("INFO", f"Attempting to update event {event_id} for '{candidate_name} @ {company}' ...")

    service = _get_calendar_service()
    if not service:
        return False

    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", DEFAULT_CALENDAR_ID)
    try:
        event_body = _build_event_body(interview_data, candidate_name)
        _log("INFO", f"DEBUG: Updating event body in Google: {event_body}")
        service.events().update(
            calendarId=calendar_id, eventId=event_id, body=event_body
        ).execute()
        _log("INFO", f"Event UPDATED successfully!")
        _log("INFO", f"  → Event ID : {event_id}")
        _log("INFO", f"  → Title    : {event_body['summary']}")
        return True
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        _log("ERROR", f"Failed to update event {event_id}: {e}\nFull Traceback:\n{error_details}")
        return False


def delete_calendar_event(event_id: str) -> bool:
    """
    Deletes a Google Calendar event.
    Returns True on success, False on failure.
    Only runs in production (APP_ENV=production).
    """
    app_env = os.getenv("APP_ENV", "local").strip().lower()
    if app_env != "production":
        _log("INFO", f"Skipping calendar DELETE — APP_ENV='{app_env}' (not production)")
        return False

    if not event_id:
        _log("WARN", "Delete skipped — no gcal_event_id stored for this interview")
        return False

    _log("INFO", f"Attempting to delete event {event_id} ...")

    service = _get_calendar_service()
    if not service:
        return False

    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", DEFAULT_CALENDAR_ID)
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        _log("INFO", f"Event DELETED successfully! (Event ID: {event_id})")
        return True
    except Exception as e:
        _log("ERROR", f"Failed to delete event {event_id}: {e}")
        return False

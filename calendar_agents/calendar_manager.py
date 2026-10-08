"""
Google Calendar Manager - Handles all Google Calendar API operations.
"""

import os
import pickle
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import CALENDAR_CLIENT_CONFIG, CALENDAR_SCOPES, TIMEZONE


class GoogleCalendarManager:
    """Manages Google Calendar operations."""

    def __init__(self, token_path: str = "token.pickle"):
        self.token_path = token_path
        self.service = None
        self._authenticated = False

    def authenticate(self) -> bool:
        """Authenticate with Google Calendar API."""
        try:
            creds = None

            if os.path.exists(self.token_path):
                with open(self.token_path, "rb") as token:
                    creds = pickle.load(token)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_config(
                        CALENDAR_CLIENT_CONFIG, CALENDAR_SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                with open(self.token_path, "wb") as token:
                    pickle.dump(creds, token)

            self.service = build("calendar", "v3", credentials=creds)
            self._authenticated = True
            return True

        except Exception as e:
            print(f"Authentication failed: {e}")
            return False

    def ensure_authenticated(self):
        """Ensure we have valid authentication."""
        if not self._authenticated:
            self.authenticate()

    def list_events(
        self, start_date: datetime = None, end_date: datetime = None, max_results: int = 50
    ) -> list[dict]:
        """List events from Google Calendar."""
        self.ensure_authenticated()

        if start_date is None:
            start_date = datetime.utcnow()
        if end_date is None:
            end_date = start_date + timedelta(days=14)

        events_result = (
            self.service.events()
            .list(
                calendarId="primary",
                timeMin=start_date.isoformat() + "Z",
                timeMax=end_date.isoformat() + "Z",
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        return events_result.get("items", [])

    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        location: str = None,
        description: str = None,
    ) -> dict:
        """Create an event in Google Calendar."""
        self.ensure_authenticated()

        event = {
            "summary": title,
            "start": {"dateTime": start_time, "timeZone": TIMEZONE},
            "end": {"dateTime": end_time, "timeZone": TIMEZONE},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 15}]},
        }

        if location:
            event["location"] = location
        if description:
            event["description"] = description

        created = self.service.events().insert(calendarId="primary", body=event).execute()

        return {"id": created.get("id"), "link": created.get("htmlLink"), "status": "created"}

    def delete_event(self, event_id: str) -> dict:
        """Delete an event from Google Calendar."""
        self.ensure_authenticated()

        self.service.events().delete(calendarId="primary", eventId=event_id).execute()

        return {"id": event_id, "status": "deleted"}

    def update_event(self, event_id: str, updates: dict) -> dict:
        """Update an event in Google Calendar."""
        self.ensure_authenticated()

        event = self.service.events().get(calendarId="primary", eventId=event_id).execute()

        if "title" in updates:
            event["summary"] = updates["title"]
        if "location" in updates:
            event["location"] = updates["location"]
        if "start_time" in updates:
            event["start"] = {"dateTime": updates["start_time"], "timeZone": TIMEZONE}
        if "end_time" in updates:
            event["end"] = {"dateTime": updates["end_time"], "timeZone": TIMEZONE}

        updated = (
            self.service.events()
            .update(calendarId="primary", eventId=event_id, body=event)
            .execute()
        )

        return {"id": updated.get("id"), "link": updated.get("htmlLink"), "status": "updated"}

    def find_conflicts(self, start_time: str, end_time: str) -> list[dict]:
        """Find events that conflict with a given time range."""
        self.ensure_authenticated()

        start_dt = datetime.fromisoformat(start_time.replace("Z", ""))
        end_dt = datetime.fromisoformat(end_time.replace("Z", ""))

        events = self.list_events(
            start_date=start_dt - timedelta(hours=1), end_date=end_dt + timedelta(hours=1)
        )

        conflicts = []
        for event in events:
            event_start = event["start"].get("dateTime", event["start"].get("date"))
            event_end = event["end"].get("dateTime", event["end"].get("date"))

            if "T" in event_start:
                e_start = datetime.fromisoformat(event_start.split("+")[0].replace("Z", ""))
                e_end = datetime.fromisoformat(event_end.split("+")[0].replace("Z", ""))

                # Check for overlap
                if not (e_end <= start_dt or e_start >= end_dt):
                    conflicts.append(event)

        return conflicts

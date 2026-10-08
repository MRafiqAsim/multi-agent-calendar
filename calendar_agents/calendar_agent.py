"""
CalendarAgent - Handles all Google Calendar operations.
Uses openai-agents library with @function_tool decorator pattern.
"""

import json
from datetime import datetime, timedelta

from agents import Agent, function_tool

from .calendar_manager import GoogleCalendarManager
from .config import OPENAI_DEPLOYMENT_NAME, TIMEZONE

# Global calendar manager instance (initialized on first use)
_calendar_manager = None


def get_calendar_manager() -> GoogleCalendarManager:
    """Get or create the calendar manager singleton."""
    global _calendar_manager
    if _calendar_manager is None:
        _calendar_manager = GoogleCalendarManager()
        _calendar_manager.authenticate()
    return _calendar_manager


# CALENDAR FUNCTION TOOLS


@function_tool
def create_calendar_event(
    title: str, date: str, start_time: str, end_time: str, location: str = "", description: str = ""
) -> str:
    """
    Create a new event in Google Calendar.

    Args:
        title: Event title/name
        date: Event date in YYYY-MM-DD format
        start_time: Start time in HH:MM format (24-hour)
        end_time: End time in HH:MM format (24-hour)
        location: Event location (optional)
        description: Event description (optional)

    Returns:
        Success message with event details or error message
    """
    try:
        manager = get_calendar_manager()

        start_datetime = f"{date}T{start_time}:00"
        end_datetime = f"{date}T{end_time}:00"

        result = manager.create_event(
            title=title,
            start_time=start_datetime,
            end_time=end_datetime,
            location=location if location else None,
            description=description or f"Event: {title}",
        )

        return f"Event created successfully! Title: '{title}' on {date} from {start_time} to {end_time}. Link: {result.get('link', 'N/A')}"

    except Exception as e:
        return f"Failed to create event: {str(e)}"


@function_tool
def list_calendar_events(days: int = 14) -> str:
    """
    List upcoming events from Google Calendar.

    Args:
        days: Number of days to look ahead (default 14)

    Returns:
        JSON string with list of events
    """
    try:
        manager = get_calendar_manager()

        now = datetime.now()
        end_date = now + timedelta(days=days)

        events = manager.list_events(start_date=now, end_date=end_date)

        if not events:
            return json.dumps({"events": [], "message": "No upcoming events found."})

        event_list = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            event_list.append(
                {
                    "id": event.get("id"),
                    "title": event.get("summary", "Untitled"),
                    "start": start,
                    "end": end,
                    "location": event.get("location", ""),
                }
            )

        return json.dumps({"events": event_list, "count": len(event_list)})

    except Exception as e:
        return json.dumps({"error": str(e), "events": []})


@function_tool
def list_events_for_date(date: str) -> str:
    """
    List events for a specific date.

    Args:
        date: Date in YYYY-MM-DD format

    Returns:
        JSON string with events for that date
    """
    try:
        manager = get_calendar_manager()

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start_of_day = date_obj.replace(hour=0, minute=0, second=0)
        end_of_day = date_obj.replace(hour=23, minute=59, second=59)

        events = manager.list_events(start_date=start_of_day, end_date=end_of_day)

        event_list = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))

            start_time = ""
            end_time = ""
            if "T" in start:
                start_time = start.split("T")[1][:5]
                end_time = end.split("T")[1][:5]

            event_list.append(
                {
                    "id": event.get("id"),
                    "title": event.get("summary", "Untitled"),
                    "start_time": start_time,
                    "end_time": end_time,
                    "location": event.get("location", ""),
                }
            )

        return json.dumps({"date": date, "events": event_list, "count": len(event_list)})

    except Exception as e:
        return json.dumps({"error": str(e), "events": []})


@function_tool
def delete_calendar_event(event_title: str, event_date: str = "") -> str:
    """
    Delete an event from Google Calendar by title.

    Args:
        event_title: Title of the event to delete (exact or partial match)
        event_date: Optional date in YYYY-MM-DD format to narrow search

    Returns:
        Success or error message
    """
    try:
        manager = get_calendar_manager()

        # Determine search range
        if event_date:
            date_obj = datetime.strptime(event_date, "%Y-%m-%d")
            start_date = date_obj.replace(hour=0, minute=0, second=0)
            end_date = date_obj.replace(hour=23, minute=59, second=59)
        else:
            now = datetime.now()
            start_date = now
            end_date = now + timedelta(days=30)

        events = manager.list_events(start_date=start_date, end_date=end_date)
        event_title_lower = event_title.lower().strip()

        # First try exact match
        for event in events:
            event_summary = event.get("summary", "")
            if event_summary.lower().strip() == event_title_lower:
                manager.delete_event(event["id"])
                return f"Successfully deleted event: '{event_summary}'"

        # Then try partial match
        for event in events:
            event_summary = event.get("summary", "")
            if event_title_lower in event_summary.lower():
                manager.delete_event(event["id"])
                return f"Successfully deleted event: '{event_summary}'"

        # List available events if not found
        available_events = [e.get("summary", "Untitled") for e in events[:10]]
        if available_events:
            return f"No event found matching '{event_title}'. Available events: {', '.join(available_events)}"
        else:
            return f"No event found matching '{event_title}'. No events in the search range."

    except Exception as e:
        return f"Failed to delete event: {str(e)}"


@function_tool
def update_calendar_event(
    event_title: str,
    new_date: str = "",
    new_start_time: str = "",
    new_end_time: str = "",
    new_location: str = "",
) -> str:
    """
    Update an existing event in Google Calendar.

    Args:
        event_title: Title of the event to update (partial match)
        new_date: New date in YYYY-MM-DD format (optional)
        new_start_time: New start time in HH:MM format (optional)
        new_end_time: New end time in HH:MM format (optional)
        new_location: New location (optional)

    Returns:
        Success or error message
    """
    try:
        manager = get_calendar_manager()

        # Search next 30 days
        now = datetime.now()
        events = manager.list_events(start_date=now, end_date=now + timedelta(days=30))

        event_title_lower = event_title.lower()

        for event in events:
            if event_title_lower in event.get("summary", "").lower():
                updates = {}

                # Get current date/time
                current_start = event["start"].get("dateTime", "")

                if current_start and "T" in current_start:
                    current_date = current_start.split("T")[0]
                    current_start_time = current_start.split("T")[1][:5]
                    current_end = event["end"].get("dateTime", "")
                    current_end_time = (
                        current_end.split("T")[1][:5] if current_end else current_start_time
                    )
                else:
                    current_date = current_start
                    current_start_time = "09:00"
                    current_end_time = "10:00"

                # Apply updates
                final_date = new_date if new_date else current_date
                final_start = new_start_time if new_start_time else current_start_time
                final_end = new_end_time if new_end_time else current_end_time

                updates["start_time"] = f"{final_date}T{final_start}:00"
                updates["end_time"] = f"{final_date}T{final_end}:00"

                if new_location:
                    updates["location"] = new_location

                manager.update_event(event["id"], updates)

                return f"Successfully updated event '{event.get('summary')}' to {final_date} from {final_start} to {final_end}"

        return f"No event found matching: '{event_title}'"

    except Exception as e:
        return f"Failed to update event: {str(e)}"


@function_tool
def find_free_slots(date: str, start_hour: int = 9, end_hour: int = 17) -> str:
    """
    Find free time slots on a specific date.

    Args:
        date: Date in YYYY-MM-DD format
        start_hour: Start of working hours (default 9)
        end_hour: End of working hours (default 17)

    Returns:
        JSON with scheduled events and available time slots
    """
    try:
        manager = get_calendar_manager()

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start_of_day = date_obj.replace(hour=0, minute=0, second=0)
        end_of_day = date_obj.replace(hour=23, minute=59, second=59)

        events = manager.list_events(start_date=start_of_day, end_date=end_of_day)

        # Build busy slots
        busy_slots = []
        for event in events:
            start = event["start"].get("dateTime", "")
            end = event["end"].get("dateTime", "")

            if start and "T" in start:
                start_dt = datetime.fromisoformat(start.split("+")[0].replace("Z", ""))
                end_dt = datetime.fromisoformat(end.split("+")[0].replace("Z", ""))

                start_h = start_dt.hour + start_dt.minute / 60
                end_h = end_dt.hour + end_dt.minute / 60

                if start_h < end_hour and end_h > start_hour:
                    busy_slots.append(
                        {
                            "title": event.get("summary", "Untitled"),
                            "start": start_dt.strftime("%H:%M"),
                            "end": end_dt.strftime("%H:%M"),
                            "start_hour": start_h,
                            "end_hour": end_h,
                        }
                    )

        busy_slots.sort(key=lambda x: x["start_hour"])

        # Find free slots
        free_slots = []
        current = start_hour

        for slot in busy_slots:
            slot_start = max(slot["start_hour"], start_hour)
            if current < slot_start:
                free_slots.append(
                    {
                        "start": f"{int(current):02d}:{int((current % 1) * 60):02d}",
                        "end": f"{int(slot_start):02d}:{int((slot_start % 1) * 60):02d}",
                    }
                )
            current = max(current, slot["end_hour"])

        if current < end_hour:
            free_slots.append(
                {
                    "start": f"{int(current):02d}:{int((current % 1) * 60):02d}",
                    "end": f"{end_hour:02d}:00",
                }
            )

        return json.dumps(
            {
                "date": date,
                "date_formatted": date_obj.strftime("%A, %B %d, %Y"),
                "time_range": f"{start_hour:02d}:00 - {end_hour:02d}:00",
                "scheduled_events": [
                    {"title": s["title"], "start": s["start"], "end": s["end"]} for s in busy_slots
                ],
                "free_slots": free_slots,
            }
        )

    except Exception as e:
        return json.dumps({"error": str(e)})


# CALENDAR SCHEDULER AGENT - Using openai-agents Agent class


def create_calendar_scheduler_agent(date_helper_agent_tool=None) -> Agent:
    """Create the Calendar Scheduler Agent with all calendar tools."""
    tools = [
        create_calendar_event,
        list_calendar_events,
        list_events_for_date,
        delete_calendar_event,
        update_calendar_event,
        find_free_slots,
    ]

    # Add date helper as a tool if provided
    if date_helper_agent_tool:
        tools.append(date_helper_agent_tool)

    return Agent(
        name="Calendar Scheduler Pro",
        model=OPENAI_DEPLOYMENT_NAME,
        instructions=f"""You are an expert calendar scheduling assistant with access to Google Calendar.

Your primary job is to help users manage their calendar efficiently and accurately.

CAPABILITIES:
1. CREATE events - schedule new events
2. LIST events - show calendar/schedule
3. UPDATE events - reschedule or modify events
4. DELETE events - cancel/remove events
5. FIND FREE SLOTS - show available time slots

WHEN SCHEDULING NEW EVENTS:
1. Extract key details: title, date, start time, end time, location, description
2. If ANY required information is missing (title, date, start_time, end_time), ask the user for clarification
3. BEFORE creating any event, use list_events_for_date() to check for conflicts
4. If conflicts exist, inform the user and ask how to proceed
5. Use ONLY the create_calendar_event function to schedule events
6. Always confirm successful scheduling with event details

REQUIRED INFORMATION FOR NEW EVENTS:
- Title: The name of the event (NEVER assume generic names like "Meeting")
- Date: When the event takes place
- Start Time: When the event begins
- End Time: When the event ends (or duration to calculate it)

WHEN DELETING/CANCELING EVENTS:
1. If user says "cancel" or "delete", use delete_calendar_event
2. User may refer to event by title, time, or description from previous conversation
3. If title is generic like "Meeting", proceed with deletion - do NOT ask for more details
4. If multiple events could match, list them and ask which one to delete
5. Confirm deletion after successful removal

WHEN UPDATING EVENTS:
1. Identify the event by title (partial match is fine)
2. Apply the requested changes (new time, date, location)
3. Confirm the update with new details

FORMATTING REQUIREMENTS:
- Dates: Use YYYY-MM-DD format (e.g., {datetime.now().year}-12-10)
- Times: Use 24-hour format HH:MM (e.g., 14:30 for 2:30 PM)
- If user gives 12-hour format, convert to 24-hour

CURRENT CONTEXT:
- Today's Date: {datetime.now().strftime("%Y-%m-%d")} ({datetime.now().strftime("%A")})
- Current Year: {datetime.now().year}
- Timezone: {TIMEZONE}

COMMUNICATION STYLE:
- Be friendly and professional
- Always confirm details before creating NEW events
- For deletions, proceed if event title is clear
- Provide clear success/failure messages""",
        tools=tools,
    )


class CalendarAgent:
    """
    Handles all Google Calendar operations.
    Maintains backward compatibility with the old interface.
    """

    def __init__(self):
        self.manager = get_calendar_manager()

    def list_events(
        self, days: int = 14, start_date: datetime = None, end_date: datetime = None
    ) -> list[dict]:
        """Get events from Google Calendar with optional date range."""
        if start_date is None:
            start_date = datetime.now()
        if end_date is None:
            end_date = start_date + timedelta(days=days)
        return self.manager.list_events(start_date=start_date, end_date=end_date)

    def list_events_for_date(self, target_date: str) -> list[dict]:
        """Get events for a specific date (YYYY-MM-DD format)."""
        date_obj = datetime.strptime(target_date, "%Y-%m-%d")
        start_of_day = date_obj.replace(hour=0, minute=0, second=0)
        end_of_day = date_obj.replace(hour=23, minute=59, second=59)
        return self.manager.list_events(start_date=start_of_day, end_date=end_of_day)

    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        location: str = None,
        description: str = None,
        event_type: str = None,
    ) -> dict:
        """Create event in Google Calendar."""
        full_description = description or f"Event: {title}"
        if event_type:
            full_description = f"[{event_type.upper()}] {full_description}"

        return self.manager.create_event(title, start_time, end_time, location, full_description)

    def delete_event(self, event_id: str) -> dict:
        """Delete event from Google Calendar."""
        return self.manager.delete_event(event_id)

    def update_event(self, event_id: str, updates: dict) -> dict:
        """Update event in Google Calendar."""
        return self.manager.update_event(event_id, updates)

    def find_event_by_title(self, title: str, days: int = 30) -> dict | None:
        """Find an event by its title (case-insensitive partial match)."""
        events = self.list_events(days=days)
        title_lower = title.lower()
        for event in events:
            if title_lower in event.get("summary", "").lower():
                return event
        return None

    def create_multiple_events(self, events_data: list[dict]) -> dict:
        """Create multiple events at once."""
        results = {"created": [], "failed": []}

        for event_data in events_data:
            try:
                date = event_data.get("date", datetime.now().strftime("%Y-%m-%d"))
                start_time = event_data.get("start_time", "09:00")
                end_time = event_data.get("end_time", "10:00")

                start_datetime = f"{date}T{start_time}:00"
                end_datetime = f"{date}T{end_time}:00"

                result = self.create_event(
                    title=event_data.get("title", "Untitled Event"),
                    start_time=start_datetime,
                    end_time=end_datetime,
                    location=event_data.get("location"),
                    description=event_data.get("description"),
                    event_type=event_data.get("type"),
                )
                results["created"].append(
                    {
                        "title": event_data.get("title"),
                        "id": result.get("id"),
                        "link": result.get("link"),
                    }
                )
            except Exception as e:
                results["failed"].append({"title": event_data.get("title"), "error": str(e)})

        return results

"""
CollaborationAgent - Coordinates batch operations and conflict resolution.
Uses openai-agents library with @function_tool decorator pattern.
"""

import json
from datetime import datetime

from agents import Agent, function_tool

from .calendar_agent import (
    CalendarAgent,
    find_free_slots,
    list_calendar_events,
    list_events_for_date,
)
from .config import OPENAI_DEPLOYMENT_NAME, TIMEZONE

# COLLABORATION FUNCTION TOOLS

# Global references for tools (will be set during initialization)
_calendar_agent = None
_conflict_agent = None


def set_collaboration_agents(calendar_agent, conflict_agent):
    """Set the agent references for collaboration tools."""
    global _calendar_agent, _conflict_agent
    _calendar_agent = calendar_agent
    _conflict_agent = conflict_agent


@function_tool
def execute_batch_import(events_json: str, skip_conflicts: bool = True) -> str:
    """
    Execute batch creation of multiple events with conflict handling.

    Args:
        events_json: JSON string containing list of events to create
        skip_conflicts: If True, skip events that conflict. If False, create anyway.

    Returns:
        JSON string with results: created, skipped, and failed events
    """
    global _calendar_agent, _conflict_agent

    try:
        events = json.loads(events_json) if isinstance(events_json, str) else events_json

        results = {"created": [], "skipped": [], "failed": []}

        for event_data in events:
            try:
                # Build datetime strings
                date = event_data.get("date")
                start_time = event_data.get("start_time", "09:00")
                end_time = event_data.get("end_time", "10:00")

                if not date:
                    results["failed"].append(
                        {"title": event_data.get("title"), "error": "Missing date"}
                    )
                    continue

                start_datetime = f"{date}T{start_time}:00"
                end_datetime = f"{date}T{end_time}:00"

                # Check for conflicts
                if skip_conflicts and _conflict_agent:
                    conflicts = _conflict_agent.check_conflicts(start_datetime, end_datetime)
                    if conflicts:
                        results["skipped"].append(
                            {
                                "title": event_data.get("title"),
                                "reason": f"Conflicts with: {', '.join([c.get('summary', 'Unknown') for c in conflicts])}",
                            }
                        )
                        continue

                # Create the event
                if _calendar_agent:
                    result = _calendar_agent.create_event(
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
                            "date": date,
                            "time": f"{start_time} - {end_time}",
                        }
                    )

            except Exception as e:
                results["failed"].append({"title": event_data.get("title"), "error": str(e)})

        return json.dumps(
            {
                "success": True,
                "summary": f"Created: {len(results['created'])}, Skipped: {len(results['skipped'])}, Failed: {len(results['failed'])}",
                "results": results,
            }
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@function_tool
def resolve_scheduling_conflict(
    choice: str,
    event_title: str = "",
    event_date: str = "",
    event_start_time: str = "",
    event_end_time: str = "",
    conflict_event_id: str = "",
    new_date: str = "",
    new_start_time: str = "",
    new_end_time: str = "",
) -> str:
    """
    Resolve a scheduling conflict based on user choice.

    Args:
        choice: Resolution choice - 'force_create', 'reschedule_existing', 'new_time', or 'cancel'
        event_title: Title of the new event (for force_create or new_time)
        event_date: Date of the new event (YYYY-MM-DD)
        event_start_time: Start time (HH:MM)
        event_end_time: End time (HH:MM)
        conflict_event_id: ID of conflicting event (for reschedule_existing)
        new_date: New date for rescheduling (YYYY-MM-DD)
        new_start_time: New start time for rescheduling (HH:MM)
        new_end_time: New end time for rescheduling (HH:MM)

    Returns:
        JSON string with resolution result
    """
    global _calendar_agent

    try:
        if choice == "force_create" and event_title:
            # Create event regardless of conflicts
            start_datetime = f"{event_date}T{event_start_time}:00"
            end_datetime = f"{event_date}T{event_end_time}:00"

            result = _calendar_agent.create_event(
                title=event_title, start_time=start_datetime, end_time=end_datetime
            )
            return json.dumps(
                {
                    "success": True,
                    "action": "force_create",
                    "message": f"Created event '{event_title}' despite conflicts",
                    "event": result,
                }
            )

        elif choice == "new_time" and event_title and new_start_time:
            # Create event at new time
            date = new_date if new_date else event_date
            start_datetime = f"{date}T{new_start_time}:00"
            end_datetime = f"{date}T{new_end_time}:00"

            result = _calendar_agent.create_event(
                title=event_title, start_time=start_datetime, end_time=end_datetime
            )
            return json.dumps(
                {
                    "success": True,
                    "action": "new_time",
                    "message": f"Created event '{event_title}' at new time",
                    "event": result,
                }
            )

        elif choice == "reschedule_existing" and conflict_event_id and new_start_time:
            # Move the conflicting event to a new time
            date = new_date if new_date else event_date
            result = _calendar_agent.update_event(
                conflict_event_id,
                {
                    "start_time": f"{date}T{new_start_time}:00",
                    "end_time": f"{date}T{new_end_time}:00",
                },
            )
            return json.dumps(
                {
                    "success": True,
                    "action": "reschedule_existing",
                    "message": "Rescheduled existing conflicting event",
                }
            )

        elif choice == "cancel":
            return json.dumps(
                {"success": True, "action": "cancel", "message": "Event creation cancelled"}
            )

        return json.dumps(
            {"success": False, "error": "Invalid resolution choice or missing parameters"}
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@function_tool
def analyze_schedule_optimization(date: str) -> str:
    """
    Analyze a day's schedule and suggest optimizations.

    Args:
        date: Date to analyze in YYYY-MM-DD format

    Returns:
        JSON string with analysis and optimization suggestions
    """
    global _calendar_agent, _conflict_agent

    try:
        events = _calendar_agent.list_events_for_date(date) if _calendar_agent else []
        free_slots = _conflict_agent.find_alternative_slots(date) if _conflict_agent else []

        # Parse date for display
        date_obj = datetime.strptime(date, "%Y-%m-%d")

        analysis = {
            "date": date,
            "date_formatted": date_obj.strftime("%A, %B %d, %Y"),
            "total_events": len(events),
            "events": [],
            "free_slots": free_slots,
            "suggestions": [],
        }

        # Analyze events
        for event in events:
            analysis["events"].append(
                {
                    "title": event.get("summary"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                }
            )

        # Generate suggestions
        if len(events) > 5:
            analysis["suggestions"].append("Consider spreading meetings across multiple days")
        if len(free_slots) == 0:
            analysis["suggestions"].append(
                "Your day is fully booked - consider rescheduling non-urgent items"
            )
        elif any(slot["duration_minutes"] < 30 for slot in free_slots):
            analysis["suggestions"].append(
                "Some free slots are very short - consider consolidating meetings"
            )
        if len(events) == 0:
            analysis["suggestions"].append("No events scheduled - a good day for focused work!")

        return json.dumps(analysis)

    except Exception as e:
        return json.dumps({"error": str(e), "date": date})


@function_tool
def get_collaboration_status() -> str:
    """
    Get information about the collaboration agent capabilities.

    Returns:
        JSON string with collaboration agent info
    """
    return json.dumps(
        {
            "agent": "CollaborationAgent",
            "capabilities": [
                "Batch import of multiple events",
                "Conflict detection during batch operations",
                "Conflict resolution (force create, reschedule, cancel)",
                "Schedule optimization analysis",
            ],
            "status": "ready",
        }
    )


# =============================================================================
# COLLABORATION AGENT - Using openai-agents Agent class
# =============================================================================


def create_collaboration_agent() -> Agent:
    """Create the Collaboration Agent with batch operation tools."""
    return Agent(
        name="Batch Operations Coordinator",
        model=OPENAI_DEPLOYMENT_NAME,
        instructions=f"""You are an expert batch operations coordinator for calendar management.

Your primary job is to handle bulk event operations and coordinate conflict resolution.

CAPABILITIES:
1. Batch import multiple events from parsed schedules
2. Detect conflicts during batch operations
3. Resolve conflicts with user choices
4. Analyze and optimize daily schedules

BATCH IMPORT WORKFLOW:
1. Receive list of events to create
2. Check each event for conflicts
3. Create non-conflicting events
4. Skip or flag conflicting events based on settings
5. Report results: created, skipped, failed

CONFLICT RESOLUTION OPTIONS:
- force_create: Create event despite conflicts (double-book)
- new_time: Create event at a different time
- reschedule_existing: Move the conflicting event
- cancel: Cancel the new event creation

CURRENT CONTEXT:
- Today's Date: {datetime.now().strftime("%Y-%m-%d")}
- Current Year: {datetime.now().year}
- Timezone: {TIMEZONE}

COMMUNICATION STYLE:
- Report batch results clearly
- Summarize: X created, Y skipped, Z failed
- Provide actionable options for conflicts""",
        tools=[
            execute_batch_import,
            resolve_scheduling_conflict,
            analyze_schedule_optimization,
            get_collaboration_status,
            list_calendar_events,
            list_events_for_date,
            find_free_slots,
        ],
    )


# Create the collaboration agent instance
collaboration_agent = create_collaboration_agent()


class CollaborationAgent:
    """
    Coordinates batch operations and conflict resolution.
    Maintains backward compatibility with the old interface.
    """

    def __init__(self, calendar_agent: CalendarAgent, conflict_agent):
        self.calendar_agent = calendar_agent
        self.conflict_agent = conflict_agent
        self.agent = collaboration_agent

        # Set global references for function tools
        set_collaboration_agents(calendar_agent, conflict_agent)

    def execute_batch(self, events: list[dict], skip_conflicts: bool = True) -> dict:
        """
        Execute batch creation of events with conflict handling.

        Args:
            events: List of event dictionaries to create
            skip_conflicts: If True, skip events that conflict. If False, create anyway.

        Returns:
            Dictionary with created, skipped, and failed events
        """
        results = {"created": [], "skipped": [], "failed": []}

        for event_data in events:
            try:
                # Build datetime strings
                date = event_data.get("date")
                start_time = event_data.get("start_time", "09:00")
                end_time = event_data.get("end_time", "10:00")

                if not date:
                    results["failed"].append(
                        {"title": event_data.get("title"), "error": "Missing date"}
                    )
                    continue

                start_datetime = f"{date}T{start_time}:00"
                end_datetime = f"{date}T{end_time}:00"

                # Check for conflicts
                if skip_conflicts:
                    conflicts = self.conflict_agent.check_conflicts(start_datetime, end_datetime)
                    if conflicts:
                        results["skipped"].append(
                            {
                                "title": event_data.get("title"),
                                "reason": f"Conflicts with: {', '.join([c.get('summary', 'Unknown') for c in conflicts])}",
                            }
                        )
                        continue

                # Create the event
                result = self.calendar_agent.create_event(
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
                        "date": date,
                        "time": f"{start_time} - {end_time}",
                    }
                )

            except Exception as e:
                results["failed"].append({"title": event_data.get("title"), "error": str(e)})

        return results

    def resolve_conflict(
        self,
        choice: str,
        event_data: dict = None,
        conflict_event_id: str = None,
        new_time: dict = None,
    ) -> dict:
        """
        Resolve a conflict based on user choice.

        Args:
            choice: 'force_create', 'reschedule_existing', 'new_time', or 'cancel'
            event_data: Original event data (for force_create or new_time)
            conflict_event_id: ID of conflicting event (for reschedule_existing)
            new_time: New time slot {date, start_time, end_time}

        Returns:
            Result of the resolution
        """
        if choice == "force_create" and event_data:
            return self.calendar_agent.create_event(
                title=event_data.get("title"),
                start_time=event_data.get("start_time"),
                end_time=event_data.get("end_time"),
                location=event_data.get("location"),
                description=event_data.get("description"),
                event_type=event_data.get("type"),
            )

        elif choice == "new_time" and event_data and new_time:
            date = new_time.get("date", event_data.get("date"))
            start = new_time.get("start_time")
            end = new_time.get("end_time")

            start_datetime = f"{date}T{start}:00"
            end_datetime = f"{date}T{end}:00"

            return self.calendar_agent.create_event(
                title=event_data.get("title"),
                start_time=start_datetime,
                end_time=end_datetime,
                location=event_data.get("location"),
                description=event_data.get("description"),
                event_type=event_data.get("type"),
            )

        elif choice == "reschedule_existing" and conflict_event_id and new_time:
            return self.calendar_agent.update_event(
                conflict_event_id,
                {
                    "start_time": f"{new_time['date']}T{new_time['start_time']}:00",
                    "end_time": f"{new_time['date']}T{new_time['end_time']}:00",
                },
            )

        elif choice == "cancel":
            return {"status": "cancelled", "message": "Event creation cancelled"}

        return {"status": "error", "message": "Invalid resolution choice"}

    def optimize_schedule(self, date: str) -> dict:
        """
        Analyze and suggest optimizations for a day's schedule.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Analysis and suggestions
        """
        events = self.calendar_agent.list_events_for_date(date)
        free_slots = self.conflict_agent.find_alternative_slots(date)

        analysis = {
            "date": date,
            "total_events": len(events),
            "events": [],
            "free_slots": free_slots,
            "suggestions": [],
        }

        for event in events:
            analysis["events"].append(
                {
                    "title": event.get("summary"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                }
            )

        if len(events) > 5:
            analysis["suggestions"].append("Consider spreading meetings across multiple days")
        if len(free_slots) == 0:
            analysis["suggestions"].append(
                "Your day is fully booked - consider rescheduling non-urgent items"
            )
        elif any(slot["duration_minutes"] < 30 for slot in free_slots):
            analysis["suggestions"].append(
                "Some free slots are very short - consider consolidating meetings"
            )

        return analysis

"""
ConflictAgent - Detects and analyzes scheduling conflicts.
Uses openai-agents library with @function_tool decorator pattern.
"""

import json
from datetime import datetime, timedelta

from agents import Agent, function_tool

from .calendar_agent import (
    CalendarAgent,
    find_free_slots,
    get_calendar_manager,
    list_calendar_events,
    list_events_for_date,
    update_calendar_event,
)
from .config import OPENAI_DEPLOYMENT_NAME, TIMEZONE

# =============================================================================
# CONFLICT DETECTION FUNCTION TOOLS
# =============================================================================

# Global calendar agent reference for tools
_calendar_agent_ref = None


def set_conflict_calendar_agent(calendar_agent):
    """Set the calendar agent reference for conflict tools."""
    global _calendar_agent_ref
    _calendar_agent_ref = calendar_agent


@function_tool
def check_time_conflicts(date: str, start_time: str, end_time: str) -> str:
    """
    Check for scheduling conflicts on a specific date and time range.

    Args:
        date: Date to check in YYYY-MM-DD format
        start_time: Start time in HH:MM format
        end_time: End time in HH:MM format

    Returns:
        JSON string with conflict information
    """
    global _calendar_agent_ref

    try:
        start_datetime = f"{date}T{start_time}:00"
        end_datetime = f"{date}T{end_time}:00"

        start_dt = datetime.fromisoformat(start_datetime)
        end_dt = datetime.fromisoformat(end_datetime)

        # Get events around this time
        if _calendar_agent_ref:
            events = _calendar_agent_ref.list_events(
                start_date=start_dt - timedelta(hours=2), end_date=end_dt + timedelta(hours=2)
            )
        else:
            manager = get_calendar_manager()
            events = manager.list_events(
                start_date=start_dt - timedelta(hours=2), end_date=end_dt + timedelta(hours=2)
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
                    conflicts.append(
                        {
                            "id": event.get("id"),
                            "title": event.get("summary", "Untitled"),
                            "start": e_start.strftime("%H:%M"),
                            "end": e_end.strftime("%H:%M"),
                            "overlap_type": _calculate_overlap_type(
                                start_dt, end_dt, e_start, e_end
                            ),
                        }
                    )

        if conflicts:
            severity = (
                "HIGH" if len(conflicts) > 2 else ("MEDIUM" if len(conflicts) == 2 else "LOW")
            )
        else:
            severity = "NONE"

        return json.dumps(
            {
                "has_conflicts": len(conflicts) > 0,
                "conflict_count": len(conflicts),
                "severity": severity,
                "conflicts": conflicts,
                "checked_time": f"{date} {start_time}-{end_time}",
            }
        )

    except Exception as e:
        return json.dumps({"error": str(e), "has_conflicts": False})


def _calculate_overlap_type(new_start, new_end, existing_start, existing_end) -> str:
    """Calculate the type of overlap between two time ranges."""
    if new_start <= existing_start and new_end >= existing_end:
        return "complete"  # New event completely covers existing
    elif new_start >= existing_start and new_end <= existing_end:
        return "contained"  # New event is within existing
    elif new_start < existing_start:
        return "end_overlap"  # New event overlaps at the start of existing
    else:
        return "start_overlap"  # New event overlaps at the end of existing


@function_tool
def analyze_conflict_severity(conflicts_json: str) -> str:
    """
    Analyze the severity of scheduling conflicts and provide recommendations.

    Args:
        conflicts_json: JSON string with conflict data from check_time_conflicts

    Returns:
        JSON string with severity analysis and recommendations
    """
    try:
        data = json.loads(conflicts_json) if isinstance(conflicts_json, str) else conflicts_json
        conflicts = data.get("conflicts", [])

        if not conflicts:
            return json.dumps(
                {"severity": "NONE", "message": "No conflicts detected", "recommendations": []}
            )

        # Analyze overlap types
        complete_overlaps = sum(1 for c in conflicts if c.get("overlap_type") == "complete")
        contained_overlaps = sum(1 for c in conflicts if c.get("overlap_type") == "contained")

        recommendations = []

        if complete_overlaps > 0:
            recommendations.append("Some events completely overlap - consider canceling one")
        if contained_overlaps > 0:
            recommendations.append(
                "New event is contained within existing event - consider a different time"
            )
        if len(conflicts) > 2:
            recommendations.append(
                "Multiple conflicts detected - consider rescheduling to a different day"
            )

        recommendations.append("Use find_free_slots to find available time slots")

        severity = (
            "HIGH"
            if len(conflicts) > 2 or complete_overlaps > 0
            else ("MEDIUM" if len(conflicts) == 2 else "LOW")
        )

        return json.dumps(
            {
                "severity": severity,
                "conflict_count": len(conflicts),
                "complete_overlaps": complete_overlaps,
                "partial_overlaps": len(conflicts) - complete_overlaps,
                "recommendations": recommendations,
                "conflicting_events": [c.get("title") for c in conflicts],
            }
        )

    except Exception as e:
        return json.dumps({"error": str(e), "severity": "UNKNOWN"})


@function_tool
def find_alternative_time_slots(
    date: str, duration_minutes: int = 60, start_hour: int = 9, end_hour: int = 17
) -> str:
    """
    Find available time slots on a specific date that can fit an event.

    Args:
        date: Date to search in YYYY-MM-DD format
        duration_minutes: Required duration in minutes (default 60)
        start_hour: Start of search window (default 9)
        end_hour: End of search window (default 17)

    Returns:
        JSON string with available time slots
    """
    global _calendar_agent_ref

    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start_of_day = date_obj.replace(hour=start_hour, minute=0)
        end_of_day = date_obj.replace(hour=end_hour, minute=0)

        # Get existing events
        if _calendar_agent_ref:
            events = _calendar_agent_ref.list_events_for_date(date)
        else:
            manager = get_calendar_manager()
            events = manager.list_events(start_date=start_of_day, end_date=end_of_day)

        # Build list of busy periods
        busy_periods = []
        for event in events:
            event_start = event["start"].get("dateTime", event["start"].get("date"))
            event_end = event["end"].get("dateTime", event["end"].get("date"))

            if "T" in event_start:
                e_start = datetime.fromisoformat(event_start.split("+")[0].replace("Z", ""))
                e_end = datetime.fromisoformat(event_end.split("+")[0].replace("Z", ""))
                busy_periods.append((e_start, e_end, event.get("summary", "Untitled")))

        busy_periods.sort(key=lambda x: x[0])

        # Find free slots
        free_slots = []
        current_time = start_of_day

        for busy_start, busy_end, _title in busy_periods:
            if current_time + timedelta(minutes=duration_minutes) <= busy_start:
                slot_duration = int((busy_start - current_time).total_seconds() / 60)
                if slot_duration >= duration_minutes:
                    free_slots.append(
                        {
                            "start": current_time.strftime("%H:%M"),
                            "end": busy_start.strftime("%H:%M"),
                            "duration_minutes": slot_duration,
                            "can_fit": True,
                        }
                    )
            current_time = max(current_time, busy_end)

        # Check remaining time after last event
        if current_time + timedelta(minutes=duration_minutes) <= end_of_day:
            slot_duration = int((end_of_day - current_time).total_seconds() / 60)
            free_slots.append(
                {
                    "start": current_time.strftime("%H:%M"),
                    "end": end_of_day.strftime("%H:%M"),
                    "duration_minutes": slot_duration,
                    "can_fit": True,
                }
            )

        return json.dumps(
            {
                "date": date,
                "date_formatted": date_obj.strftime("%A, %B %d, %Y"),
                "search_window": f"{start_hour:02d}:00 - {end_hour:02d}:00",
                "required_duration": duration_minutes,
                "free_slots": free_slots,
                "slots_found": len(free_slots),
                "busy_events": [
                    {"title": t, "start": s.strftime("%H:%M"), "end": e.strftime("%H:%M")}
                    for s, e, t in busy_periods
                ],
            }
        )

    except Exception as e:
        return json.dumps({"error": str(e), "free_slots": []})


@function_tool
def suggest_conflict_resolutions(
    event_title: str, event_date: str, event_start: str, event_end: str, conflicts_json: str
) -> str:
    """
    Suggest options for resolving scheduling conflicts.

    Args:
        event_title: Title of the new event
        event_date: Date of the new event (YYYY-MM-DD)
        event_start: Start time of new event (HH:MM)
        event_end: End time of new event (HH:MM)
        conflicts_json: JSON string with conflict information

    Returns:
        JSON string with resolution options
    """
    try:
        data = json.loads(conflicts_json) if isinstance(conflicts_json, str) else conflicts_json
        conflicts = data.get("conflicts", [])

        options = []

        # Option 1: Move conflicting events
        for conflict in conflicts:
            options.append(
                {
                    "action": "move_existing",
                    "event_to_move": conflict.get("title"),
                    "event_id": conflict.get("id"),
                    "description": f"Reschedule '{conflict.get('title')}' to a different time",
                }
            )

        # Option 2: Force create (double-book)
        options.append(
            {
                "action": "force_create",
                "description": f"Create '{event_title}' anyway (will result in double-booking)",
            }
        )

        # Option 3: Find alternative time
        options.append(
            {
                "action": "find_alternative",
                "description": f"Find a free time slot for '{event_title}' on {event_date}",
            }
        )

        # Option 4: Cancel
        options.append({"action": "cancel", "description": "Cancel creating this event"})

        return json.dumps(
            {
                "event": event_title,
                "requested_time": f"{event_date} {event_start}-{event_end}",
                "conflict_count": len(conflicts),
                "resolution_options": options,
            }
        )

    except Exception as e:
        return json.dumps({"error": str(e)})


@function_tool
def get_conflict_agent_status() -> str:
    """
    Get information about the conflict agent capabilities.

    Returns:
        JSON string with conflict agent info
    """
    return json.dumps(
        {
            "agent": "ConflictAgent",
            "capabilities": [
                "Detect time conflicts for new events",
                "Analyze conflict severity (LOW/MEDIUM/HIGH)",
                "Find alternative free time slots",
                "Suggest conflict resolution options",
                "Support rescheduling of conflicting events",
            ],
            "status": "ready",
        }
    )


# =============================================================================
# CONFLICT RESOLUTION AGENT - Using openai-agents Agent class
# =============================================================================


def create_conflict_resolver_agent() -> Agent:
    """Create the Conflict Resolver Agent with conflict detection tools."""
    return Agent(
        name="Conflict Resolution Specialist",
        model=OPENAI_DEPLOYMENT_NAME,
        instructions=f"""You are an expert scheduling conflict resolution specialist.

Your primary job is to detect, analyze, and help resolve scheduling conflicts.

CAPABILITIES:
1. Detect time conflicts between events
2. Analyze conflict severity (LOW, MEDIUM, HIGH)
3. Find alternative free time slots
4. Suggest resolution options
5. Help reschedule conflicting events

WHEN CHECKING FOR CONFLICTS:
1. Use check_time_conflicts() to detect overlaps
2. Use analyze_conflict_severity() to assess the situation
3. Use find_alternative_time_slots() to find open times
4. Use suggest_conflict_resolutions() to provide options

CONFLICT SEVERITY LEVELS:
- NONE: No conflicts detected
- LOW: 1 minor overlap
- MEDIUM: 2 overlaps or significant overlap
- HIGH: 3+ overlaps or complete overlap

RESOLUTION OPTIONS:
1. move_existing: Reschedule the conflicting event
2. force_create: Create anyway (double-book)
3. find_alternative: Find a different time slot
4. cancel: Cancel the new event

CURRENT CONTEXT:
- Today's Date: {datetime.now().strftime("%Y-%m-%d")}
- Current Year: {datetime.now().year}
- Timezone: {TIMEZONE}

COMMUNICATION STYLE:
- Be clear about which events conflict
- Report severity level
- Always provide actionable resolution options
- Suggest alternative time slots when possible""",
        tools=[
            check_time_conflicts,
            analyze_conflict_severity,
            find_alternative_time_slots,
            suggest_conflict_resolutions,
            get_conflict_agent_status,
            list_calendar_events,
            list_events_for_date,
            find_free_slots,
            update_calendar_event,
        ],
    )


# Create the agent instance
conflict_resolver_agent = create_conflict_resolver_agent()


class ConflictAgent:
    """
    Detects and analyzes scheduling conflicts.
    Maintains backward compatibility with the old interface.
    """

    def __init__(self, calendar_agent: CalendarAgent):
        self.calendar_agent = calendar_agent
        self.agent = conflict_resolver_agent

        # Set global reference for function tools
        set_conflict_calendar_agent(calendar_agent)

    def check_conflicts(self, start_time: str, end_time: str) -> list[dict]:
        """
        Check for conflicts with existing events.

        Args:
            start_time: ISO format datetime string
            end_time: ISO format datetime string

        Returns:
            List of conflicting events
        """
        # Parse the times
        start_dt = datetime.fromisoformat(start_time.replace("Z", ""))
        end_dt = datetime.fromisoformat(end_time.replace("Z", ""))

        # Get events around this time
        events = self.calendar_agent.list_events(
            start_date=start_dt - timedelta(hours=2), end_date=end_dt + timedelta(hours=2)
        )

        conflicts = []
        for event in events:
            event_start = event["start"].get("dateTime", event["start"].get("date"))
            event_end = event["end"].get("dateTime", event["end"].get("date"))

            if "T" in event_start:
                e_start = datetime.fromisoformat(event_start.split("+")[0].replace("Z", ""))
                e_end = datetime.fromisoformat(event_end.split("+")[0].replace("Z", ""))

                # Check for overlap: not (e_end <= start or e_start >= end)
                if not (e_end <= start_dt or e_start >= end_dt):
                    conflicts.append(event)

        return conflicts

    def analyze_severity(self, conflicts: list[dict]) -> str:
        """
        Analyze the severity of conflicts.

        Returns:
            'NONE', 'LOW', 'MEDIUM', or 'HIGH'
        """
        if not conflicts:
            return "NONE"
        elif len(conflicts) == 1:
            return "LOW"
        elif len(conflicts) == 2:
            return "MEDIUM"
        else:
            return "HIGH"

    def find_alternative_slots(
        self, date: str, duration_minutes: int = 60, start_hour: int = 9, end_hour: int = 17
    ) -> list[dict]:
        """
        Find alternative free time slots on a given date.

        Args:
            date: Date in YYYY-MM-DD format
            duration_minutes: Required duration in minutes
            start_hour: Start of business hours
            end_hour: End of business hours

        Returns:
            List of available time slots
        """
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start_of_day = date_obj.replace(hour=start_hour, minute=0)
        end_of_day = date_obj.replace(hour=end_hour, minute=0)

        # Get existing events for this day
        events = self.calendar_agent.list_events_for_date(date)

        # Build list of busy periods
        busy_periods = []
        for event in events:
            event_start = event["start"].get("dateTime", event["start"].get("date"))
            event_end = event["end"].get("dateTime", event["end"].get("date"))

            if "T" in event_start:
                e_start = datetime.fromisoformat(event_start.split("+")[0].replace("Z", ""))
                e_end = datetime.fromisoformat(event_end.split("+")[0].replace("Z", ""))
                busy_periods.append((e_start, e_end))

        # Sort by start time
        busy_periods.sort(key=lambda x: x[0])

        # Find free slots
        free_slots = []
        current_time = start_of_day

        for busy_start, busy_end in busy_periods:
            if current_time + timedelta(minutes=duration_minutes) <= busy_start:
                free_slots.append(
                    {
                        "start": current_time.strftime("%H:%M"),
                        "end": busy_start.strftime("%H:%M"),
                        "duration_minutes": int((busy_start - current_time).total_seconds() / 60),
                    }
                )
            current_time = max(current_time, busy_end)

        # Check remaining time after last event
        if current_time + timedelta(minutes=duration_minutes) <= end_of_day:
            free_slots.append(
                {
                    "start": current_time.strftime("%H:%M"),
                    "end": end_of_day.strftime("%H:%M"),
                    "duration_minutes": int((end_of_day - current_time).total_seconds() / 60),
                }
            )

        return free_slots

    def suggest_reschedule_options(self, event: dict, conflicts: list[dict]) -> list[dict]:
        """
        Suggest options for resolving a conflict.

        Returns:
            List of resolution options
        """
        options = []

        # Option 1: Keep the new event, suggest moving conflicting events
        for conflict in conflicts:
            options.append(
                {
                    "action": "move_existing",
                    "event_to_move": conflict.get("summary"),
                    "event_id": conflict.get("id"),
                    "description": f"Move '{conflict.get('summary')}' to a different time",
                }
            )

        # Option 2: Force create anyway
        options.append(
            {"action": "force_create", "description": "Create the event anyway (double-booking)"}
        )

        # Option 3: Cancel new event
        options.append({"action": "cancel", "description": "Cancel creating this event"})

        return options

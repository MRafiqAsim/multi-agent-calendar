"""
ChangeManagementAgent - Parses natural language change requests.
Uses openai-agents library with @function_tool decorator pattern.
"""

import json
import re
from datetime import datetime

from agents import Agent, function_tool

from .config import OPENAI_DEPLOYMENT_NAME, TIMEZONE
from .utils import call_openai_api, extract_json_from_response

CHANGE_MANAGEMENT_SYSTEM_PROMPT = """
You are a change management assistant for calendar events.
Parse user requests to modify existing calendar events.

Extract the following from user messages:
- event_identifier: The name or description of the event to modify
- change_type: 'reschedule', 'rename', 'relocate', 'cancel', or 'update'
- new_date: New date if rescheduling (YYYY-MM-DD format)
- new_start_time: New start time (HH:MM format)
- new_end_time: New end time (HH:MM format)
- new_title: New title if renaming
- new_location: New location if relocating

Return JSON only:
{
    "event_identifier": "event name or description",
    "change_type": "reschedule|rename|relocate|cancel|update",
    "new_date": "YYYY-MM-DD or null",
    "new_start_time": "HH:MM or null",
    "new_end_time": "HH:MM or null",
    "new_title": "new title or null",
    "new_location": "new location or null",
    "confidence": 0.0-1.0
}
"""


# =============================================================================
# CHANGE MANAGEMENT FUNCTION TOOLS
# =============================================================================


@function_tool
def parse_change_request(user_message: str, events_context: str = "") -> str:
    """
    Parse a natural language change request into structured data.

    Args:
        user_message: The user's natural language request (e.g., "move the meeting to 3pm")
        events_context: Optional context about existing events

    Returns:
        JSON string with parsed change request data
    """
    try:
        messages = [
            {"role": "system", "content": CHANGE_MANAGEMENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Events context:\n{events_context}\n\nUser request: {user_message}",
            },
        ]

        response = call_openai_api(messages, temperature=0.1, max_tokens=500)
        data = extract_json_from_response(response)

        return json.dumps({"success": True, "parsed_request": data})
    except Exception:
        # Fallback to basic parsing
        result = _basic_parse(user_message)
        return json.dumps(
            {"success": True, "parsed_request": result, "note": "Used fallback parsing"}
        )


def _basic_parse(text: str) -> dict:
    """Basic regex-based parsing as fallback."""
    result = {
        "event_identifier": None,
        "change_type": None,
        "new_date": None,
        "new_start_time": None,
        "new_end_time": None,
        "new_title": None,
        "new_location": None,
        "confidence": 0.5,
    }

    text_lower = text.lower()

    # Detect change type
    if any(word in text_lower for word in ["move", "reschedule", "change time", "postpone"]):
        result["change_type"] = "reschedule"
    elif any(word in text_lower for word in ["rename", "change name", "call it"]):
        result["change_type"] = "rename"
    elif any(word in text_lower for word in ["cancel", "delete", "remove"]):
        result["change_type"] = "cancel"
    elif any(word in text_lower for word in ["location", "room", "place", "move to"]):
        result["change_type"] = "relocate"
    else:
        result["change_type"] = "update"

    # Try to extract time (e.g., "to 2pm", "at 14:00")
    time_pattern = r"(?:to|at)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
    time_match = re.search(time_pattern, text_lower)
    if time_match:
        time_str = time_match.group(1)
        result["new_start_time"] = _parse_time(time_str)

    return result


def _parse_time(time_str: str) -> str | None:
    """Parse time string to HH:MM format."""
    time_str = time_str.lower().strip()

    # Already in HH:MM format
    if re.match(r"^\d{1,2}:\d{2}$", time_str):
        parts = time_str.split(":")
        return f"{int(parts[0]):02d}:{parts[1]}"

    # "2pm", "2 pm", etc.
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = match.group(3)

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    return None


@function_tool
def validate_change_request(change_request_json: str, existing_event_json: str = "") -> str:
    """
    Validate a parsed change request against an existing event.

    Args:
        change_request_json: JSON string with the parsed change request
        existing_event_json: Optional JSON string with the existing event data

    Returns:
        JSON string with validation result and any issues
    """
    try:
        change_data = (
            json.loads(change_request_json)
            if isinstance(change_request_json, str)
            else change_request_json
        )

        # Handle nested structure
        if "parsed_request" in change_data:
            change_data = change_data["parsed_request"]

        issues = []

        if not change_data.get("event_identifier"):
            issues.append("Could not identify which event to modify")

        if change_data.get("change_type") == "reschedule":
            if not change_data.get("new_date") and not change_data.get("new_start_time"):
                issues.append("No new date or time specified for rescheduling")

        if change_data.get("change_type") == "rename" and not change_data.get("new_title"):
            issues.append("No new title specified for renaming")

        if change_data.get("change_type") == "relocate" and not change_data.get("new_location"):
            issues.append("No new location specified for relocating")

        return json.dumps({"valid": len(issues) == 0, "issues": issues, "change_data": change_data})

    except Exception as e:
        return json.dumps(
            {"valid": False, "issues": [f"Validation error: {str(e)}"], "change_data": None}
        )


@function_tool
def detect_change_intent(user_message: str) -> str:
    """
    Quickly detect the type of change the user wants to make.

    Args:
        user_message: The user's message

    Returns:
        JSON string with detected intent
    """
    text_lower = user_message.lower()

    intents = []

    if any(
        word in text_lower for word in ["move", "reschedule", "change time", "postpone", "push"]
    ):
        intents.append("reschedule")
    if any(word in text_lower for word in ["rename", "change name", "call it", "change title"]):
        intents.append("rename")
    if any(word in text_lower for word in ["cancel", "delete", "remove", "drop"]):
        intents.append("cancel")
    if any(word in text_lower for word in ["location", "room", "place", "where", "venue"]):
        intents.append("relocate")
    if any(word in text_lower for word in ["update", "change", "modify", "edit"]):
        intents.append("update")

    if not intents:
        intents.append("unknown")

    return json.dumps(
        {
            "message": user_message,
            "detected_intents": intents,
            "primary_intent": intents[0] if intents else "unknown",
        }
    )


@function_tool
def get_change_management_status() -> str:
    """
    Get information about the change management agent capabilities.

    Returns:
        JSON string with change management agent info
    """
    return json.dumps(
        {
            "agent": "ChangeManagementAgent",
            "capabilities": [
                "Parse natural language change requests",
                "Detect change intent (reschedule, rename, cancel, etc.)",
                "Validate change requests",
                "Extract new dates, times, titles, locations from requests",
            ],
            "supported_change_types": [
                "reschedule - Change date/time of event",
                "rename - Change title of event",
                "relocate - Change location of event",
                "cancel - Delete/remove event",
                "update - General modification",
            ],
            "status": "ready",
        }
    )


# CHANGE MANAGEMENT AGENT - Using openai-agents Agent class


def create_change_management_agent() -> Agent:
    """Create the Change Management Agent with request parsing tools."""
    return Agent(
        name="Change Request Parser",
        model=OPENAI_DEPLOYMENT_NAME,
        instructions=f"""You are an expert at parsing natural language requests to modify calendar events.

Your primary job is to understand what changes users want to make to their calendar events.

CAPABILITIES:
1. Parse change requests into structured data
2. Detect change intent (reschedule, rename, cancel, etc.)
3. Validate change requests
4. Extract specific details (new time, new title, etc.)

CHANGE TYPES:
- reschedule: Move event to different date/time
- rename: Change event title
- relocate: Change event location
- cancel: Delete/remove event
- update: General modification

PARSING EXAMPLES:
- "Move the meeting to 3pm" → reschedule, new_start_time: "15:00"
- "Cancel my dentist appointment" → cancel, event_identifier: "dentist appointment"
- "Change the team sync to Room 201" → relocate, new_location: "Room 201"
- "Rename the standup to Daily Sync" → rename, new_title: "Daily Sync"

CURRENT CONTEXT:
- Today's Date: {datetime.now().strftime("%Y-%m-%d")}
- Current Year: {datetime.now().year}
- Timezone: {TIMEZONE}

COMMUNICATION STYLE:
- Parse requests accurately
- Ask for clarification if ambiguous
- Report confidence level in parsing
- Validate before applying changes""",
        tools=[
            parse_change_request,
            validate_change_request,
            detect_change_intent,
            get_change_management_status,
        ],
    )


# Create the change management agent instance
change_management_agent = create_change_management_agent()


class ChangeManagementAgent:
    """
    Parses natural language change requests for calendar events.
    Maintains backward compatibility with the old interface.
    """

    def __init__(self):
        self.agent = change_management_agent

    def parse_request(self, user_message: str, events_context: str = "") -> dict:
        """
        Parse a user's change request into structured data.

        Args:
            user_message: The user's natural language request
            events_context: Context about existing events

        Returns:
            Structured change request data
        """
        messages = [
            {"role": "system", "content": CHANGE_MANAGEMENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Events context:\n{events_context}\n\nUser request: {user_message}",
            },
        ]

        try:
            response = call_openai_api(messages, temperature=0.1, max_tokens=500)
            data = extract_json_from_response(response)
            return data
        except Exception:
            # Fallback to basic parsing
            return self._basic_parse(user_message)

    def _basic_parse(self, text: str) -> dict:
        """Basic regex-based parsing as fallback."""
        return _basic_parse(text)

    def _parse_time(self, time_str: str) -> str | None:
        """Parse time string to HH:MM format."""
        return _parse_time(time_str)

    def validate_change(self, change_data: dict, existing_event: dict) -> dict:
        """
        Validate a change request against an existing event.

        Returns:
            Validation result with any issues
        """
        issues = []

        if not change_data.get("event_identifier"):
            issues.append("Could not identify which event to modify")

        if change_data.get("change_type") == "reschedule":
            if not change_data.get("new_date") and not change_data.get("new_start_time"):
                issues.append("No new date or time specified for rescheduling")

        if change_data.get("change_type") == "rename" and not change_data.get("new_title"):
            issues.append("No new title specified for renaming")

        return {"valid": len(issues) == 0, "issues": issues, "change_data": change_data}

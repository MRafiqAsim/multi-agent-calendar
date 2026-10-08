"""
DateHelperAgent - Helper agent for date and time calculations.
Uses openai-agents library with @function_tool decorator pattern.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any

from agents import Agent, function_tool

from .config import OPENAI_DEPLOYMENT_NAME

# =============================================================================
# DATE HELPER FUNCTION TOOLS
# =============================================================================


@function_tool
def get_current_date() -> str:
    """Get the current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


@function_tool
def get_current_datetime_info() -> str:
    """Get comprehensive current datetime information including weekday and week number."""
    now = datetime.now()
    return json.dumps(
        {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "weekday": now.strftime("%A"),
            "week_number": now.isocalendar()[1],
            "year": now.year,
            "formatted": now.strftime("%A, %B %d, %Y at %H:%M"),
        }
    )


def _parse_relative_date_internal(text: str) -> str:
    """Internal function to parse relative date expressions to YYYY-MM-DD format."""
    today = datetime.now()
    text = text.lower().strip()

    if text in ["today", "now"]:
        return today.strftime("%Y-%m-%d")
    elif text == "tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif text == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # "next monday", "next tuesday", etc.
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(weekdays):
        if f"next {day}" in text or text == day:
            current_day = today.weekday()
            days_ahead = i - current_day
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # "in X days" pattern
    in_days_match = re.search(r"in\s+(\d+)\s+days?", text)
    if in_days_match:
        days_num = int(in_days_match.group(1))
        return (today + timedelta(days=days_num)).strftime("%Y-%m-%d")

    # "December 10", "Dec 10", etc.
    months = {
        "january": 1,
        "jan": 1,
        "february": 2,
        "feb": 2,
        "march": 3,
        "mar": 3,
        "april": 4,
        "apr": 4,
        "may": 5,
        "june": 6,
        "jun": 6,
        "july": 7,
        "jul": 7,
        "august": 8,
        "aug": 8,
        "september": 9,
        "sep": 9,
        "sept": 9,
        "october": 10,
        "oct": 10,
        "november": 11,
        "nov": 11,
        "december": 12,
        "dec": 12,
    }

    for month_name, month_num in months.items():
        pattern = rf"{month_name}\s+(\d{{1,2}})"
        match = re.search(pattern, text)
        if match:
            day_num = int(match.group(1))
            year = today.year
            # If the date has passed this year, use next year
            try:
                date = datetime(year, month_num, day_num)
                if date < today:
                    date = datetime(year + 1, month_num, day_num)
                return date.strftime("%Y-%m-%d")
            except ValueError:
                pass

    return None


# Keep the old function name as an alias for backward compatibility
parse_relative_date = _parse_relative_date_internal


@function_tool
def calculate_date_from_relative(relative_date: str) -> str:
    """
    Calculate actual date from relative expressions.

    Args:
        relative_date: Relative date like 'tomorrow', 'next Monday', 'in 3 days'

    Returns:
        JSON with resolved date information
    """
    result_date = _parse_relative_date_internal(relative_date)

    if result_date:
        dt = datetime.strptime(result_date, "%Y-%m-%d")
        return json.dumps(
            {
                "success": True,
                "original": relative_date,
                "resolved_date": result_date,
                "weekday": dt.strftime("%A"),
                "formatted": dt.strftime("%A, %B %d, %Y"),
            }
        )

    return json.dumps(
        {
            "success": False,
            "original": relative_date,
            "error": f"Could not parse relative date: {relative_date}",
        }
    )


def parse_time_expression(text: str) -> str:
    """Parse time expressions to HH:MM format."""
    text = text.lower().strip()

    # Already in HH:MM format
    if re.match(r"^\d{1,2}:\d{2}$", text):
        parts = text.split(":")
        return f"{int(parts[0]):02d}:{parts[1]}"

    # "2pm", "2 pm", "14:00", etc.
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
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


def calculate_duration(start_time: str, end_time: str) -> int:
    """Calculate duration in minutes between two times."""
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    diff = end - start
    return int(diff.total_seconds() / 60)


@function_tool
def calculate_end_time(start_time: str, duration_minutes: int) -> str:
    """
    Calculate end time given start time and duration.

    Args:
        start_time: Start time in HH:MM format
        duration_minutes: Duration in minutes

    Returns:
        End time in HH:MM format
    """
    try:
        parts = start_time.split(":")
        start_minutes = int(parts[0]) * 60 + int(parts[1])
        end_minutes = start_minutes + duration_minutes

        if end_minutes >= 24 * 60:
            end_minutes = end_minutes % (24 * 60)

        hours = end_minutes // 60
        minutes = end_minutes % 60
        return f"{hours:02d}:{minutes:02d}"
    except Exception as e:
        return f"Error: {str(e)}"


def validate_datetime(date_str: str, time_str: str) -> tuple:
    """Validate date and time strings."""
    errors = []

    if date_str:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            errors.append(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")

    if time_str:
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                errors.append(f"Invalid time: {time_str}. Hour must be 0-23, minute 0-59")
        except (ValueError, IndexError):
            errors.append(f"Invalid time format: {time_str}. Expected HH:MM")

    if errors:
        return False, "; ".join(errors)
    return True, ""


# =============================================================================
# DATE HELPER AGENT - Using openai-agents Agent class
# =============================================================================


def create_date_helper_agent() -> Agent:
    """Create the Date Time Helper Agent with all date/time tools."""
    return Agent(
        name="Date Time Helper",
        model=OPENAI_DEPLOYMENT_NAME,
        instructions=f"""You are an expert date and time calculation assistant.

Your primary job is to help with date/time calculations and conversions.

CAPABILITIES:
1. Get current date and time information
2. Calculate dates from relative expressions (tomorrow, next Monday, in 3 days)
3. Calculate end times from start times and durations
4. Provide formatted date information

CURRENT CONTEXT:
- Today's Date: {datetime.now().strftime("%Y-%m-%d")}
- Current Year: {datetime.now().year}
- Day of Week: {datetime.now().strftime("%A")}

FORMATTING REQUIREMENTS:
- Dates: Always use YYYY-MM-DD format (e.g., {datetime.now().year}-12-10)
- Times: Always use 24-hour format HH:MM (e.g., 14:30 for 2:30 PM)

COMMUNICATION STYLE:
- Be precise and accurate
- Return clear, formatted responses
- Always include the day of week when providing dates""",
        tools=[
            get_current_date,
            get_current_datetime_info,
            calculate_date_from_relative,
            calculate_end_time,
        ],
    )


# Create the agent instance
date_helper_agent = create_date_helper_agent()


class DateHelperAgent:
    """
    Helper agent for date and time calculations.
    Provides date-related utilities that other agents can delegate to.
    This class maintains backward compatibility with the old interface.
    """

    def __init__(self):
        self.agent = date_helper_agent

    def get_current_date(self) -> str:
        """Get the current date in YYYY-MM-DD format."""
        return datetime.now().strftime("%Y-%m-%d")

    def get_current_datetime_info(self) -> dict[str, Any]:
        """Get comprehensive datetime information."""
        now = datetime.now()
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "weekday": now.strftime("%A"),
            "week_number": now.isocalendar()[1],
            "year": now.year,
        }

    def resolve_relative_date(self, text: str) -> dict[str, Any]:
        """Resolve relative date expressions like 'tomorrow', 'next Monday', etc."""
        resolved = _parse_relative_date_internal(text)
        if resolved:
            dt = datetime.strptime(resolved, "%Y-%m-%d")
            return {
                "success": True,
                "original": text,
                "resolved_date": resolved,
                "weekday": dt.strftime("%A"),
                "formatted": dt.strftime("%A, %B %d, %Y"),
            }
        return {
            "success": False,
            "original": text,
            "error": f"Could not parse date expression: {text}",
        }

    def resolve_time(self, text: str) -> dict[str, Any]:
        """Resolve time expressions like '2pm', '14:30', etc."""
        resolved = parse_time_expression(text)
        if resolved:
            return {
                "success": True,
                "original": text,
                "resolved_time": resolved,
                "formatted_12h": datetime.strptime(resolved, "%H:%M").strftime("%I:%M %p"),
            }
        return {
            "success": False,
            "original": text,
            "error": f"Could not parse time expression: {text}",
        }

    def calculate_duration(self, start_time: str, end_time: str) -> dict[str, Any]:
        """Calculate duration between two times."""
        duration_val = calculate_duration(start_time, end_time)
        return {"start": start_time, "end": end_time, "duration": duration_val}

    def calculate_end_time_dict(self, start_time: str, duration_minutes: int) -> dict[str, Any]:
        """Calculate end time given start time and duration."""
        end = calculate_end_time(start_time, duration_minutes)
        return {"start_time": start_time, "duration_minutes": duration_minutes, "end_time": end}

    def validate_datetime(self, date_str: str = None, time_str: str = None) -> dict[str, Any]:
        """Validate date and time strings."""
        is_valid, error = validate_datetime(date_str or "", time_str or "")
        return {
            "date": date_str,
            "time": time_str,
            "is_valid": is_valid,
            "error": error if not is_valid else None,
        }

    def get_next_weekday(self, weekday: str) -> dict[str, Any]:
        """Get the next occurrence of a specific weekday."""
        result = self.resolve_relative_date(f"next {weekday}")
        return result

    def get_week_dates(self) -> dict[str, str]:
        """Get all dates for the current week."""
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        week_dates = {}
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(days):
            week_dates[day] = (monday + timedelta(days=i)).strftime("%Y-%m-%d")
        return week_dates

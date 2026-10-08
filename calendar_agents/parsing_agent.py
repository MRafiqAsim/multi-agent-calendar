"""
ParsingAgent - Extracts events from images using GPT-4o Vision.
Uses openai-agents library with @function_tool decorator pattern.
"""

import base64
import json
from datetime import datetime

import requests
from agents import Agent, function_tool

from .config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    OPENAI_DEPLOYMENT_NAME,
    OPENAI_VERSION,
)
from .utils import extract_json_from_response

# System prompt for image-based event extraction
IMAGE_PARSING_SYSTEM_PROMPT = """
You are an expert academic schedule extraction assistant with vision capabilities.
Your goal is to analyze images of class timetables and extract all visible classes for the entire week.

Current date: {today_date}
Current weekday: {today_weekday}
Current ISO week number: {today_week_number}

EXTRACTION RULES:
1. Carefully examine the image for any weekly schedule information.
2. Extract ALL class entries for ALL days visible in the schedule (Monday through Friday/Sunday).
3. For each class entry, extract: start time, end time, subject name, and any notes (e.g., 'even weeks', 'odd weeks', 'week 1-6', etc.).
4. If the class applies only to certain weeks, check whether {today_week_number} fits the condition:
   - If the note says "even weeks" and {today_week_number} is even → include it.
   - If the note says "odd weeks" and {today_week_number} is odd → include it.
   - If the note says "week X–Y" → include only if {today_week_number} is within that range.
5. For each day, calculate the correct date based on the current week.

RESPONSE FORMAT:
Return the extracted events in this JSON structure:
{{
    "events": [
        {{
            "title": "Course name from image",
            "date": "YYYY-MM-DD",
            "start_time": "HH:MM",
            "end_time": "HH:MM",
            "location": "Location if visible, else null",
            "type": "lecture|practice|lab|exam|other",
            "description": "Additional notes like week restrictions"
        }}
    ]
}}

ADDITIONAL RULES:
- Use 24-hour time format (HH:MM).
- Merge cells or notes (like "PC-oefeningen" or "practicum") into the same activity field if relevant.
- Translate Dutch day or week labels (e.g. "even weken", "oneven weken", "maandag", "dinsdag") into English meaning when applying logic.
- Return only valid JSON output — no extra explanations, no markdown code blocks.
"""


# User prompt for image analysis
IMAGE_PARSING_USER_PROMPT = """
Please analyze the attached image of a weekly class timetable and extract all lessons or events visible in the schedule.

Current context:
- Today's date: {today_date}
- Today is: {today_weekday}
- Current ISO week number: {today_week_number}

Instructions:
- Extract all lessons from ALL days visible in the timetable.
- For each lesson, include:
  - Subject or course name (as title)
  - The correct date (calculate based on the day column and current week)
  - Start and end time
  - Notes such as "even weeks", "odd weeks", or "week ranges"
  - Type (e.g., lecture, practice, lab)
- If a note restricts the class to certain weeks, only include it if {today_week_number} matches the condition.
  - Example: include "even weeks" only if this is an even week.

Output requirements:
- Use the JSON format specified in the system prompt
- Use 24-hour time format
- Do not add explanations or text outside the JSON output
"""


# =============================================================================
# PARSING FUNCTION TOOLS
# =============================================================================


def _parse_image_internal(image_path: str) -> list[dict]:
    """
    Internal function to extract schedule events from an image using GPT-4o vision.

    Args:
        image_path: Path to the image file

    Returns:
        List of extracted event dictionaries
    """
    try:
        # Get current date info for context
        today = datetime.now()
        today_date = today.strftime("%Y-%m-%d")
        today_weekday = today.strftime("%A")
        today_week_number = today.isocalendar()[1]

        # Read and encode the image
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        # Determine image type
        if image_path.lower().endswith(".png"):
            media_type = "image/png"
        elif image_path.lower().endswith(".gif"):
            media_type = "image/gif"
        else:
            media_type = "image/jpeg"

        # Azure OpenAI API call with vision
        api_url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{OPENAI_DEPLOYMENT_NAME}/chat/completions?api-version={OPENAI_VERSION}"

        headers = {"Content-Type": "application/json", "api-key": AZURE_OPENAI_API_KEY}

        # Format prompts with current date info
        formatted_system_prompt = IMAGE_PARSING_SYSTEM_PROMPT.format(
            today_date=today_date, today_weekday=today_weekday, today_week_number=today_week_number
        )
        formatted_user_prompt = IMAGE_PARSING_USER_PROMPT.format(
            today_date=today_date, today_weekday=today_weekday, today_week_number=today_week_number
        )

        # Payload with image and text
        payload = {
            "messages": [
                {"role": "system", "content": formatted_system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": formatted_user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_data}"},
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": 4000,
        }

        # Make the API call
        response = requests.post(api_url, headers=headers, json=payload, timeout=120)

        # Parse the response
        response_data = response.json()

        # Check for API errors
        if "error" in response_data:
            print(f"API Error: {response_data['error']}")
            return []

        if "choices" not in response_data or len(response_data["choices"]) == 0:
            print(f"No choices in response: {response_data}")
            return []

        content = response_data["choices"][0]["message"]["content"]
        print(f"GPT-4o Vision raw response:\n{content[:500]}...")

        # Extract JSON from response
        try:
            data = extract_json_from_response(content)
            events = data.get("events", [])
            print(f"Extracted {len(events)} events")
            return events
        except Exception as e:
            print(f"JSON extraction error: {e}")
            print(f"Raw content: {content}")
            return []

    except FileNotFoundError:
        print(f'Error: Image file "{image_path}" not found.')
        return []
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return []


@function_tool
def parse_schedule_image(image_path: str) -> str:
    """
    Extract calendar events from an uploaded schedule image using GPT-4o Vision.

    Args:
        image_path: Path to the schedule image file (PNG, JPG, JPEG)

    Returns:
        JSON string with extracted events or error message
    """
    try:
        events = _parse_image_internal(image_path)

        if not events:
            return json.dumps(
                {"success": False, "events": [], "message": "No events found in the image"}
            )

        return json.dumps(
            {
                "success": True,
                "events": events,
                "count": len(events),
                "message": f"Successfully extracted {len(events)} events from image",
            }
        )
    except Exception as e:
        return json.dumps(
            {"success": False, "events": [], "message": f"Error parsing image: {str(e)}"}
        )


@function_tool
def get_parsing_status() -> str:
    """
    Get information about the parsing agent capabilities.

    Returns:
        JSON string with parsing agent info
    """
    return json.dumps(
        {
            "agent": "ParsingAgent",
            "capabilities": [
                "Extract events from schedule images",
                "Support for PNG, JPG, JPEG, WebP formats",
                "Automatic date calculation based on current week",
                "Week restriction handling (even/odd weeks, week ranges)",
            ],
            "supported_formats": ["png", "jpg", "jpeg", "webp"],
            "status": "ready",
        }
    )


# =============================================================================
# PARSING AGENT - Using openai-agents Agent class
# =============================================================================


def create_parsing_agent() -> Agent:
    """Create the Parsing Agent with image extraction tools."""
    return Agent(
        name="Schedule Parsing Specialist",
        model=OPENAI_DEPLOYMENT_NAME,
        instructions=f"""You are an expert schedule parsing assistant with image analysis capabilities.

Your primary job is to extract calendar events from uploaded schedule images.

CAPABILITIES:
1. Parse schedule images (timetables, calendars, screenshots)
2. Extract event details: title, date, time, location, type
3. Handle week restrictions (even/odd weeks, week ranges)
4. Calculate correct dates based on current week

CURRENT CONTEXT:
- Today's Date: {datetime.now().strftime("%Y-%m-%d")}
- Current Year: {datetime.now().year}
- Current Week: {datetime.now().isocalendar()[1]}
- Day of Week: {datetime.now().strftime("%A")}

EXTRACTION RULES:
- Use 24-hour time format (HH:MM)
- Use YYYY-MM-DD date format
- Include location if visible
- Categorize events: lecture, practice, lab, exam, other

COMMUNICATION STYLE:
- Report number of events found
- List extracted events clearly
- Mention any parsing issues or warnings""",
        tools=[
            parse_schedule_image,
            get_parsing_status,
        ],
    )


# Create the parsing agent instance
parsing_agent = create_parsing_agent()


class ParsingAgent:
    """
    Extracts events from images/PDFs using GPT-4o Vision.
    Maintains backward compatibility with the old interface.
    """

    def __init__(self):
        self.agent = parsing_agent

    def parse_image(self, image_path: str) -> list[dict]:
        """
        Extract schedule events from an image using GPT-4o vision capabilities.

        Args:
            image_path: Path to the image file

        Returns:
            List of extracted event dictionaries
        """
        return _parse_image_internal(image_path)

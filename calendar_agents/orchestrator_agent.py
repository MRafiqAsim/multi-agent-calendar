"""
OrchestratorAgent - Central coordinator for all agents.
Routes user requests to appropriate agents and manages state.
Uses openai-agents library with Agent/Runner pattern.
"""

import asyncio
from datetime import datetime

from agents import Agent, Runner

from .calendar_agent import CalendarAgent, create_calendar_scheduler_agent
from .change_management_agent import ChangeManagementAgent, change_management_agent
from .collaboration_agent import CollaborationAgent, collaboration_agent
from .config import OPENAI_DEPLOYMENT_NAME, TIMEZONE
from .conflict_agent import ConflictAgent, conflict_resolver_agent
from .date_helper_agent import (
    DateHelperAgent,
    date_helper_agent,
    get_current_date,
    get_current_datetime_info,
)
from .parsing_agent import ParsingAgent, parsing_agent

# =============================================================================
# TRIAGE/ORCHESTRATOR AGENT - Main Orchestrator using openai-agents
# =============================================================================


def create_triage_agent() -> Agent:
    """
    Create the main Triage/Orchestrator Agent that routes to specialists.
    This follows the pattern from main_app_mai.ipynb with improved prompts.
    """
    # Create the calendar scheduler agent with date helper as a tool
    calendar_agent = create_calendar_scheduler_agent(
        date_helper_agent_tool=date_helper_agent.as_tool(
            tool_name="date_time_helper",
            tool_description="Expert assistant for date calculations. Use for relative dates like 'tomorrow', 'next Monday', 'in 3 days', or to calculate end times from duration.",
        )
    )

    return Agent(
        name="Calendar Assistant",
        model=OPENAI_DEPLOYMENT_NAME,
        instructions=f"""You are the main calendar management assistant that coordinates with specialist agents.

Your primary job is to understand user requests and route them to the appropriate specialist.

AVAILABLE SPECIALIST AGENTS:

1. **calendar_scheduler** - For CRUD operations on calendar
   - CREATE: "schedule a meeting", "create an event", "book a slot"
   - READ: "show my calendar", "what's on tomorrow", "list events"
   - UPDATE: "move the meeting to 3pm", "change the time"
   - DELETE: "cancel the meeting", "delete the event", "remove"
   - FREE SLOTS: "find free time", "when am I available"

2. **conflict_resolver** - For conflict detection and resolution
   - "check for conflicts"
   - "any double bookings"
   - "is there a scheduling conflict"
   - "find overlapping events"

3. **parsing_agent** - For extracting events from images/schedules
   - "parse this schedule"
   - "extract events from image"
   - When user uploads an image

4. **collaboration_agent** - For batch operations
   - "add all these events"
   - "import multiple events"
   - "batch create"
   - "optimize my schedule"

5. **change_management** - For parsing change requests
   - "move the meeting to..."
   - "reschedule the..."
   - "rename the event to..."
   - "change the location to..."

ROUTING RULES:

1. **CANCEL/DELETE requests** → calendar_scheduler
   - "cancel the meeting", "delete Meeting", "remove the 9am event"

2. **CREATE/SCHEDULE requests** → calendar_scheduler
   - "schedule a meeting", "create an event", "book a slot"

3. **VIEW/LIST requests** → calendar_scheduler
   - "show my calendar", "what's on tomorrow", "find free slots"

4. **CONFLICT requests** → conflict_resolver
   - "check for conflicts", "any double bookings"

5. **BATCH/IMPORT requests** → collaboration_agent
   - "add all events", "import schedule", "batch create"

6. **CHANGE/UPDATE requests** → change_management (to parse) → calendar_scheduler (to execute)
   - "move meeting to 3pm", "reschedule to tomorrow"

CONTEXT AWARENESS:
- When user says "cancel 1" or "delete the first one", they're referring to a previously discussed event
- Pass along any context about events mentioned (title, time, date)
- If user mentions "Meeting" as a title, that IS the title - don't ask for more details

CURRENT CONTEXT:
- Today's Date: {datetime.now().strftime("%Y-%m-%d")} ({datetime.now().strftime("%A")})
- Current Year: {datetime.now().year}
- Timezone: {TIMEZONE}

IMPORTANT:
- CANCEL and DELETE mean the same thing - remove an event
- If user wants to cancel/delete, do NOT ask them to schedule
- Pass event details (title, time) from user's message to the specialist
- For complex changes, use change_management to parse, then calendar_scheduler to execute

COMMUNICATION STYLE:
- Be friendly and helpful
- Confirm actions taken
- Be concise""",
        tools=[
            # Date/Time tools (direct access)
            get_current_date,
            get_current_datetime_info,
            # Calendar Scheduler Agent (main CRUD operations)
            calendar_agent.as_tool(
                tool_name="calendar_scheduler",
                tool_description="Expert calendar assistant for: creating events, listing schedule, updating events, DELETING/CANCELING events, finding free slots. For deletions, pass the event title directly.",
            ),
            # Conflict Resolver Agent
            conflict_resolver_agent.as_tool(
                tool_name="conflict_resolver",
                tool_description="Expert assistant for checking and resolving scheduling conflicts, detecting double bookings, and finding alternative time slots.",
            ),
            # Parsing Agent (for image/schedule extraction)
            parsing_agent.as_tool(
                tool_name="parsing_agent",
                tool_description="Expert assistant for extracting calendar events from images, screenshots of schedules, and timetables using GPT-4o Vision.",
            ),
            # Collaboration Agent (for batch operations)
            collaboration_agent.as_tool(
                tool_name="collaboration_agent",
                tool_description="Expert assistant for batch operations: importing multiple events, bulk scheduling, conflict resolution during batch imports, and schedule optimization.",
            ),
            # Change Management Agent (for parsing change requests)
            change_management_agent.as_tool(
                tool_name="change_management",
                tool_description="Expert assistant for parsing natural language change requests like 'move meeting to 3pm', 'reschedule to tomorrow', 'rename event to...'. Extracts structured change data.",
            ),
        ],
    )


# Create the triage agent instance
triage_agent = create_triage_agent()


async def run_agent_async(user_message: str, conversation_context: str = "") -> str:
    """Run the triage agent with user message and conversation context."""
    try:
        # Build input with context if available
        if conversation_context:
            full_input = f"""CONVERSATION CONTEXT (for reference):
{conversation_context}

CURRENT USER REQUEST:
{user_message}

IMPORTANT: Focus on the CURRENT USER REQUEST. Use the context only to understand references like "the meeting" or "cancel it"."""
        else:
            full_input = user_message

        result = await Runner.run(starting_agent=triage_agent, input=full_input, max_turns=10)

        return result.final_output
    except Exception as e:
        return f"Error: {str(e)}"


def run_agent_sync(user_message: str, conversation_context: str = "") -> str:
    """Synchronous wrapper to run the agent."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_agent_async(user_message, conversation_context))
    finally:
        loop.close()


def build_conversation_context(history: list, max_turns: int = 5) -> str:
    """Build conversation context from recent history."""
    if not history:
        return ""

    # Get last N turns
    recent = history[-(max_turns * 2) :]  # Each turn has user + assistant

    context_parts = []
    for msg in recent:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            context_parts.append(f"User: {content}")
        elif role == "assistant":
            # Truncate long assistant responses
            if len(content) > 300:
                content = content[:300] + "..."
            context_parts.append(f"Assistant: {content}")

    return "\n".join(context_parts)


class OrchestratorAgent:
    """
    Central coordinator for the multi-agent calendar system.
    Routes requests to appropriate agents and manages conversation state.
    Uses openai-agents library with Agent/Runner pattern.
    """

    def __init__(self):
        # Initialize all agents (maintaining backward compatibility)
        self.date_helper = DateHelperAgent()
        self.parsing_agent = ParsingAgent()
        self.calendar_agent = CalendarAgent()
        self.conflict_agent = ConflictAgent(self.calendar_agent)
        self.change_agent = ChangeManagementAgent()
        self.collaboration_agent = CollaborationAgent(self.calendar_agent, self.conflict_agent)

        # The main triage agent using openai-agents
        self.agent = triage_agent

        # State management
        self.pending_event = {}
        self.parsed_events = []
        self.pending_update = {}
        self.pending_conflict = {}

        print("All agents initialized (using openai-agents library):")
        print("  - Date Time Helper Agent")
        print("  - Calendar Scheduler Pro Agent")
        print("  - Conflict Resolution Specialist Agent")
        print("  - Parsing Agent (GPT-4o Vision)")
        print("  - Collaboration Agent (Batch Operations)")
        print("  - Change Management Agent")
        print("  - Triage/Orchestrator Agent (main orchestrator)")

    def process_message(self, message: str, history: list = None) -> str:
        """Process user message using the openai-agents Runner."""
        try:
            # Check for parsed events confirmation
            if self.parsed_events and message.lower() in [
                "yes",
                "yeah",
                "sure",
                "ok",
                "confirm",
                "add them",
            ]:
                return self._add_parsed_events_to_calendar()

            # Build context from conversation history
            context = build_conversation_context(history or [])

            # Run the agent synchronously
            response = run_agent_sync(message.strip(), context)

            return response

        except Exception as e:
            return f"Error processing request: {str(e)}"

    def process_file(self, file_path: str) -> str:
        """Process uploaded schedule image using ParsingAgent."""
        if not file_path:
            return "No file uploaded."

        try:
            events = self.parsing_agent.parse_image(file_path)

            if not events:
                return "No events found in the image."

            self.parsed_events = events

            lines = [f"**Found {len(events)} events:**\n"]
            for e in events:
                title = e.get("title") or e.get("activity", "Untitled")
                date = e.get("date", "")
                start = e.get("start_time", "")
                end = e.get("end_time", "")
                location = e.get("location", "")
                event_type = e.get("type", "")

                lines.append(f"- **{title}**")
                if date:
                    lines.append(f"  Date: {date}")
                lines.append(f"  Time: {start} - {end}")
                if location:
                    lines.append(f"  Location: {location}")
                if event_type:
                    lines.append(f"  Type: {event_type}")

            lines.append(
                "\n**Click 'Yes' to add these to your Google Calendar, or 'No' to cancel.**"
            )

            return "\n".join(lines)

        except Exception as e:
            return f"Error: {str(e)}"

    def _add_parsed_events_to_calendar(self) -> str:
        """Add parsed events using CollaborationAgent."""
        if not self.parsed_events:
            return "No parsed events to add."

        results = self.collaboration_agent.execute_batch(self.parsed_events, skip_conflicts=True)

        lines = ["**Batch Import Results:**\n"]
        lines.append(f"Created: {len(results['created'])}")
        lines.append(f"Skipped: {len(results['skipped'])}")
        lines.append(f"Failed: {len(results['failed'])}")

        if results["created"]:
            lines.append("\n**Created:**")
            for e in results["created"]:
                lines.append(f"- {e['title']}")

        if results["skipped"]:
            lines.append("\n**Skipped (conflicts):**")
            for e in results["skipped"]:
                lines.append(f"- {e['title']}: {e.get('reason', 'Unknown')}")

        if results["failed"]:
            lines.append("\n**Failed:**")
            for e in results["failed"]:
                lines.append(f"- {e['title']}: {e.get('error', 'Unknown error')}")

        self.parsed_events = []
        return "\n".join(lines)

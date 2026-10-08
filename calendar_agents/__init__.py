# Agents Package
# Modular multi-agent system for Google Calendar management
# Uses openai-agents library for Agent/Runner pattern

# Calendar Agent and tools
from .calendar_agent import (
    CalendarAgent,
    create_calendar_event,
    create_calendar_scheduler_agent,
    delete_calendar_event,
    find_free_slots,
    get_calendar_manager,
    list_calendar_events,
    list_events_for_date,
    update_calendar_event,
)
from .calendar_manager import GoogleCalendarManager

# Change Management Agent and tools
from .change_management_agent import (
    ChangeManagementAgent,
    change_management_agent,
    create_change_management_agent,
    detect_change_intent,
    get_change_management_status,
    parse_change_request,
    validate_change_request,
)

# Collaboration Agent and tools
from .collaboration_agent import (
    CollaborationAgent,
    analyze_schedule_optimization,
    collaboration_agent,
    create_collaboration_agent,
    execute_batch_import,
    get_collaboration_status,
    resolve_scheduling_conflict,
)
from .config import (
    AZURE_ASYNC_CLIENT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    CALENDAR_CLIENT_CONFIG,
    CALENDAR_SCOPES,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    OPENAI_DEPLOYMENT_NAME,
    OPENAI_VERSION,
    TIMEZONE,
)

# Conflict Agent and tools
from .conflict_agent import (
    ConflictAgent,
    analyze_conflict_severity,
    check_time_conflicts,
    conflict_resolver_agent,
    create_conflict_resolver_agent,
    find_alternative_time_slots,
    get_conflict_agent_status,
    suggest_conflict_resolutions,
)

# Date Helper Agent and tools
from .date_helper_agent import (
    DateHelperAgent,
    calculate_date_from_relative,
    calculate_end_time,
    date_helper_agent,
    get_current_date,
    get_current_datetime_info,
    parse_relative_date,
    parse_time_expression,
)

# Orchestrator Agent and runner functions
from .orchestrator_agent import (
    OrchestratorAgent,
    build_conversation_context,
    create_triage_agent,
    run_agent_async,
    run_agent_sync,
    triage_agent,
)

# Parsing Agent and tools
from .parsing_agent import (
    ParsingAgent,
    create_parsing_agent,
    get_parsing_status,
    parse_schedule_image,
    parsing_agent,
)
from .utils import call_openai_api, encode_image_to_base64, extract_json_from_response

__all__ = [
    # Config
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "OPENAI_DEPLOYMENT_NAME",
    "OPENAI_VERSION",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "TIMEZONE",
    "CALENDAR_SCOPES",
    "CALENDAR_CLIENT_CONFIG",
    "AZURE_ASYNC_CLIENT",
    # Utils
    "encode_image_to_base64",
    "extract_json_from_response",
    "call_openai_api",
    # Calendar Manager
    "GoogleCalendarManager",
    "get_calendar_manager",
    # Date Helper Agent
    "DateHelperAgent",
    "date_helper_agent",
    "get_current_date",
    "get_current_datetime_info",
    "calculate_date_from_relative",
    "calculate_end_time",
    "parse_relative_date",
    "parse_time_expression",
    # Parsing Agent
    "ParsingAgent",
    "parsing_agent",
    "create_parsing_agent",
    "parse_schedule_image",
    "get_parsing_status",
    # Calendar Agent
    "CalendarAgent",
    "create_calendar_scheduler_agent",
    "create_calendar_event",
    "list_calendar_events",
    "list_events_for_date",
    "delete_calendar_event",
    "update_calendar_event",
    "find_free_slots",
    # Conflict Agent
    "ConflictAgent",
    "conflict_resolver_agent",
    "create_conflict_resolver_agent",
    "check_time_conflicts",
    "analyze_conflict_severity",
    "find_alternative_time_slots",
    "suggest_conflict_resolutions",
    "get_conflict_agent_status",
    # Change Management Agent
    "ChangeManagementAgent",
    "change_management_agent",
    "create_change_management_agent",
    "parse_change_request",
    "validate_change_request",
    "detect_change_intent",
    "get_change_management_status",
    # Collaboration Agent
    "CollaborationAgent",
    "collaboration_agent",
    "create_collaboration_agent",
    "execute_batch_import",
    "resolve_scheduling_conflict",
    "analyze_schedule_optimization",
    "get_collaboration_status",
    # Orchestrator Agent
    "OrchestratorAgent",
    "triage_agent",
    "create_triage_agent",
    "run_agent_async",
    "run_agent_sync",
    "build_conversation_context",
]

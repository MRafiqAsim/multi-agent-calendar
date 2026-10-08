"""
Google Calendar Manager - Main Application
AI-powered schedule management with multi-agent system.
Uses openai-agents library for Agent/Runner pattern.

Usage:
    python app.py

This is the modular version using the agents package.
"""

import os

import gradio as gr

from calendar_agents import (
    OPENAI_DEPLOYMENT_NAME,
    TIMEZONE,
    OrchestratorAgent,
)


def create_gradio_app():
    """
    Create the Gradio application with multi-agent system.
    All changes happen on Google Calendar via the API.
    """
    # Initialize the orchestrator with all agents
    orchestrator = OrchestratorAgent()

    def chat_response(message: str, history: list) -> str:
        """Processing chat message."""
        if not message or not message.strip():
            return "Please enter a message."

        try:
            response = orchestrator.process_message(message.strip(), history)
            return response
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "credential" in error_msg.lower():
                return f"**Authentication Error**\n\nPlease check your Google Calendar credentials.\n\nDetails: {error_msg}\n\n*Agent: CalendarAgent*"
            elif "api" in error_msg.lower() or "quota" in error_msg.lower():
                return f"**API Error**\n\nThere was an issue with the API.\n\nDetails: {error_msg}\n\n*Agent: System*"
            else:
                return f"**Error**\n\nSomething went wrong: {error_msg}\n\nPlease try again or rephrase your request.\n\n*Agent: System*"

    def file_upload_response(file) -> str:
        """Process uploaded file."""
        if file is None:
            return "Please upload a schedule image (PNG, JPG, JPEG)."

        # Validate file type
        allowed_extensions = [".png", ".jpg", ".jpeg", ".webp"]
        file_ext = os.path.splitext(file.name)[1].lower()
        if file_ext not in allowed_extensions:
            return f"**Invalid File Type**\n\nPlease upload an image file ({', '.join(allowed_extensions)}).\nYou uploaded: {file_ext}"

        try:
            result = orchestrator.process_file(file.name)
            return result
        except Exception as e:
            return f"**Error Processing Image**\n\nCould not process the uploaded image.\n\nDetails: {str(e)}\n\n*Agent: ParsingAgent*"

    def confirm_import_yes():
        """Confirm and add parsed events to Google Calendar."""
        if not orchestrator.parsed_events:
            return "No events to import. Please upload a schedule image first.", None

        try:
            result = orchestrator._add_parsed_events_to_calendar()
            return result, None  # Clear the file upload after successful import
        except Exception as e:
            return (
                f"**Error Adding Events**\n\nCould not add events to calendar.\n\nDetails: {str(e)}",
                None,
            )

    def confirm_import_no():
        """Cancel import and clear the parsed events."""
        orchestrator.parsed_events = []  # Clear parsed events
        return "Import cancelled. Events cleared.", None  # Clear status and file upload

    def get_system_status() -> str:
        """Get current system status."""
        try:
            events = orchestrator.calendar_agent.list_events(days=1)
            calendar_status = "Connected"
            upcoming_count = len(events)
        except Exception:
            calendar_status = "Not Connected"
            upcoming_count = 0

        datetime_info = orchestrator.date_helper.get_current_datetime_info()

        status = f"""**System Status (openai-agents)**

Calendar: {calendar_status}
Current Date: {datetime_info["date"]} ({datetime_info["weekday"]})
Current Time: {datetime_info["time"]}
Timezone: {TIMEZONE}
Model: {OPENAI_DEPLOYMENT_NAME}
Today's Events: {upcoming_count}
"""
        return status

    # Create the interface
    with gr.Blocks(title="Google Calendar Manager") as demo:
        # Header
        gr.Markdown("""
        # Google Calendar Manager
        *AI-powered schedule management using openai-agents library*

        **Agents:** Triage (Orchestrator) | Date Helper | Calendar Scheduler | Conflict Resolver | Parsing | Collaboration | Change Manager
        """)

        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(label="Chat with your Agenda Assistant", height=450)

                with gr.Row():
                    msg = gr.Textbox(
                        label="Your message",
                        placeholder="Try: 'Schedule meeting with John tomorrow at 2pm' or 'Show my calendar'",
                        scale=4,
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)

                with gr.Row():
                    clear_btn = gr.Button("Clear Chat", variant="secondary", size="sm")
                    status_btn = gr.Button("System Status", variant="secondary", size="sm")

            with gr.Column(scale=1):
                gr.Markdown("### Upload Schedule")
                file_upload = gr.File(
                    label="Upload schedule image (PNG, JPG)", file_types=["image"]
                )
                upload_btn = gr.Button("Extract Events", variant="primary")
                upload_status = gr.Textbox(label="Import Status", interactive=False, lines=6)
                gr.Markdown("**Add events to calendar?**")
                with gr.Row():
                    confirm_yes_btn = gr.Button("Yes", variant="primary", size="sm")
                    confirm_no_btn = gr.Button("No", variant="secondary", size="sm")

                gr.Markdown("### Quick Actions")
                with gr.Column():
                    show_schedule_btn = gr.Button("Show My Calendar", variant="secondary")
                    show_today_btn = gr.Button("Today's Events", variant="secondary")
                    check_conflicts_btn = gr.Button("Check Conflicts", variant="secondary")
                    help_btn = gr.Button("Help", variant="secondary")

        # Example prompts section
        gr.Markdown("""
        ---
        ### Example Commands
        - **Create:** "Schedule a meeting with John tomorrow at 2pm"
        - **View:** "Show my events for next week" or "What's on my calendar Friday?"
        - **Update:** "Move the Team Meeting to 3pm"
        - **Delete:** "Cancel the Dentist Appointment"
        - **Conflicts:** "Check for any scheduling conflicts"
        """)

        # Event handlers
        def respond(message, chat_history):
            if chat_history is None:
                chat_history = []
            if not message or not message.strip():
                return "", chat_history

            bot_message = chat_response(message, chat_history)
            chat_history.append({"role": "user", "content": message})
            chat_history.append({"role": "assistant", "content": bot_message})
            return "", chat_history

        def upload_file(file):
            return file_upload_response(file)

        def quick_action(action, chat_history):
            if chat_history is None:
                chat_history = []
            bot_message = chat_response(action, chat_history)
            chat_history.append({"role": "user", "content": action})
            chat_history.append({"role": "assistant", "content": bot_message})
            return chat_history

        def show_status(chat_history):
            if chat_history is None:
                chat_history = []
            status = get_system_status()
            chat_history.append({"role": "user", "content": "System Status"})
            chat_history.append({"role": "assistant", "content": status})
            return chat_history

        # Connect events
        msg.submit(respond, [msg, chatbot], [msg, chatbot])
        send_btn.click(respond, [msg, chatbot], [msg, chatbot])
        clear_btn.click(lambda: [], None, chatbot)
        upload_btn.click(upload_file, file_upload, upload_status)

        # Yes/No confirmation buttons
        confirm_yes_btn.click(confirm_import_yes, None, [upload_status, file_upload])
        confirm_no_btn.click(confirm_import_no, None, [upload_status, file_upload])

        show_schedule_btn.click(
            lambda h: quick_action("Show my calendar for the next 2 weeks", h), chatbot, chatbot
        )
        show_today_btn.click(
            lambda h: quick_action("Show my events for today", h), chatbot, chatbot
        )
        check_conflicts_btn.click(
            lambda h: quick_action("Check for any scheduling conflicts", h), chatbot, chatbot
        )
        help_btn.click(
            lambda h: quick_action("What can you help me with? List all available commands.", h),
            chatbot,
            chatbot,
        )
        status_btn.click(show_status, chatbot, chatbot)

    return demo


if __name__ == "__main__":
    print("=" * 60)
    print("Starting Google Calendar Manager")
    print("Using openai-agents library for multi-agent orchestration")
    print("=" * 60)

    demo = create_gradio_app()
    demo.launch(share=False, server_name="127.0.0.1", server_port=7863)

"""
Configuration module for the multi-agent calendar system.
Loads environment variables and defines constants.
Uses openai-agents library for multi-agent orchestration.
"""

import logging
import os

from dotenv import load_dotenv

# Suppress openai-agents tracing warnings BEFORE importing
logging.getLogger("openai.agents").setLevel(logging.ERROR)
logging.getLogger("agents").setLevel(logging.ERROR)

from agents import set_default_openai_client, set_tracing_disabled  # noqa: E402
from openai import AsyncAzureOpenAI  # noqa: E402

# Disable tracing completely (we use Azure OpenAI, not OpenAI)
set_tracing_disabled(True)

# Load environment variables
load_dotenv()

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_DEPLOYMENT_NAME = os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-4o")
OPENAI_VERSION = os.getenv("OPENAI_VERSION_NAME", "2025-03-01-preview")

# Construct API URL (for direct API calls like image processing)
API_URL = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{OPENAI_DEPLOYMENT_NAME}/chat/completions?api-version={OPENAI_VERSION}"

# Google Calendar Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Brussels")

# Google Calendar API Scopes
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Google Calendar Client Configuration
CALENDAR_CLIENT_CONFIG = {
    "installed": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

# Configure Azure OpenAI clients for openai-agents library
# Async client for agent operations
AZURE_ASYNC_CLIENT = AsyncAzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=OPENAI_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)

# Set as default client for openai-agents (disable tracing to avoid errors)
set_default_openai_client(AZURE_ASYNC_CLIENT, use_for_tracing=False)

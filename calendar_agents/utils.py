"""
Utility functions for the multi-agent calendar system.
Uses openai-agents library with @function_tool decorator pattern.
"""

import base64
import json
import re

import requests

# Import function_tool from openai-agents library
from .config import API_URL, AZURE_OPENAI_API_KEY


def encode_image_to_base64(image_path: str) -> str:
    """
    Encode an image file to base64 string.

    Args:
        image_path: Path to the image file

    Returns:
        Base64 encoded string of the image
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def extract_json_from_response(llm_response: str) -> dict:
    """
    Extract JSON from LLM response string.

    Args:
        llm_response: The raw response from the LLM.

    Returns:
        Parsed JSON data as dictionary.
    """
    try:
        # Remove markdown code blocks if present
        content = llm_response.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        # Use regex to find the JSON part of the response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            raise ValueError("No JSON found in LLM response.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON: {e}") from e


def call_openai_api(messages: list, temperature: float = 0.1, max_tokens: int = 2000) -> str:
    """
    Call Azure OpenAI API with given messages.

    Args:
        messages: List of message dictionaries with role and content
        temperature: Sampling temperature (default 0.1)
        max_tokens: Maximum tokens in response

    Returns:
        Response content string from the API
    """
    headers = {"Content-Type": "application/json", "api-key": AZURE_OPENAI_API_KEY}

    payload = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}

    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    response_data = response.json()

    if "error" in response_data:
        raise Exception(f"API Error: {response_data['error']}")

    return response_data["choices"][0]["message"]["content"]

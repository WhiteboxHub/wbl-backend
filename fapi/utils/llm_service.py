import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def get_openai_client(api_key: str):
    from openai import OpenAI
    return OpenAI(api_key=api_key)

def get_gemini_client(api_key: str):
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except ImportError:
        pass
    return None

def generate_text(
    prompt: str,
    api_key: str,
    provider: str,
    system_prompt: str = "You are a highly structured expert.",
    response_format: str = "text",
) -> str:
    """Generate text string using synchronous calls for the FastAPI backend."""
    if provider == "openai":
        client = get_openai_client(api_key)
        kwargs = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 3000,
            "temperature": 0.7,
        }
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
            if "json" not in system_prompt.lower() and "json" not in prompt.lower():
                kwargs["messages"][0]["content"] += "\nReturn response in STRICT JSON format."
        
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    elif provider == "gemini":
        client = get_gemini_client(api_key)
        if not client:
            raise ValueError("google-genai is not installed")
        from google.genai import types
        model_name = "gemini-2.0-flash"
        
        config_kwargs = {
            "system_instruction": system_prompt,
            "temperature": 0.7,
        }
        if response_format == "json_object":
            config_kwargs["response_mime_type"] = "application/json"
            
        config = types.GenerateContentConfig(**config_kwargs)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        return response.text
    else:
        raise ValueError(f"Unknown provider '{provider}'")

def call_llm_with_context(
    api_key: str,
    provider: str,
    prompt: str,
    system_prompt: str = "You are a helpful AI.",
    response_format: str = "text"
) -> str:
    """
    Calls the LLM using the provided key.
    """
    if not api_key:
        raise ValueError("API key is required to call LLM.")

    return generate_text(
        prompt=prompt,
        system_prompt=system_prompt,
        api_key=api_key,
        response_format=response_format,
        provider=provider,
    )

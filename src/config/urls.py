"""URL configuration functions.

Provides functions to retrieve external service URLs from environment variables
via ConfigManager.
"""

from .config_manager import ConfigManager


def get_ollama_url() -> str:
    """Get Ollama local inference server URL from environment via ConfigManager.

    Returns:
        Ollama base URL for LLM inference
    """
    return ConfigManager.get("OLLAMA_URL")


def get_traceloop_url() -> str:
    """Get Traceloop collector URL from environment via ConfigManager.

    Returns:
        Traceloop traces endpoint URL
    """
    return ConfigManager.get("TRACELOOP_URL")


def get_telegram_api_url() -> str:
    """Get Telegram Bot API base URL from environment via ConfigManager.

    Returns:
        Telegram Bot API base URL
    """
    return ConfigManager.get("TELEGRAM_API_URL")


__all__ = [
    "get_ollama_url",
    "get_traceloop_url",
    "get_telegram_api_url",
]

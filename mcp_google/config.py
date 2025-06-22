"""
Configuration settings for the MCP Gmail, Calendar, and Google Chat server.
"""

import json
import os
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Import default settings from gmail, calendar, and google_chat modules
from mcp_google.gmail import (
    DEFAULT_CREDENTIALS_PATH as GMAIL_DEFAULT_CREDENTIALS_PATH,
    DEFAULT_TOKEN_PATH as GMAIL_DEFAULT_TOKEN_PATH,
    DEFAULT_USER_ID,
    GMAIL_SCOPES,
)

from mcp_google.calendar import (
    DEFAULT_CREDENTIALS_PATH as CALENDAR_DEFAULT_CREDENTIALS_PATH,
    DEFAULT_TOKEN_PATH as CALENDAR_DEFAULT_TOKEN_PATH,
    CALENDAR_SCOPES,
)

from mcp_google.google_chat import (
    DEFAULT_CREDENTIALS_PATH as GOOGLE_CHAT_DEFAULT_CREDENTIALS_PATH,
    DEFAULT_TOKEN_PATH as GOOGLE_CHAT_DEFAULT_TOKEN_PATH,
    GOOGLE_CHAT_SCOPES,
)


class Settings(BaseSettings):
    """
    Settings model for MCP Gmail, Calendar, and Google Chat server configuration.

    Automatically reads from environment variables with MCP_GMAIL_, MCP_CALENDAR_, or MCP_CHAT_ prefix.
    """

    # Gmail settings
    gmail_credentials_path: str = GMAIL_DEFAULT_CREDENTIALS_PATH
    gmail_token_path: str = GMAIL_DEFAULT_TOKEN_PATH
    gmail_scopes: List[str] = GMAIL_SCOPES
    gmail_user_id: str = DEFAULT_USER_ID
    gmail_max_results: int = 10

    # Calendar settings
    calendar_credentials_path: str = CALENDAR_DEFAULT_CREDENTIALS_PATH
    calendar_token_path: str = CALENDAR_DEFAULT_TOKEN_PATH
    calendar_scopes: List[str] = CALENDAR_SCOPES
    calendar_max_results: int = 50

    # Google Chat settings
    google_chat_credentials_path: str = GOOGLE_CHAT_DEFAULT_CREDENTIALS_PATH
    google_chat_token_path: str = GOOGLE_CHAT_DEFAULT_TOKEN_PATH
    google_chat_scopes: List[str] = GOOGLE_CHAT_SCOPES
    google_chat_max_results: int = 100

    # Configure environment variable settings
    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Backward compatibility properties for existing Gmail code
    @property
    def credentials_path(self) -> str:
        """Backward compatibility for Gmail credentials path."""
        return self.gmail_credentials_path

    @property
    def token_path(self) -> str:
        """Backward compatibility for Gmail token path."""
        return self.gmail_token_path

    @property
    def scopes(self) -> List[str]:
        """Backward compatibility for Gmail scopes."""
        return self.gmail_scopes

    @property
    def user_id(self) -> str:
        """Backward compatibility for Gmail user ID."""
        return self.gmail_user_id

    @property
    def max_results(self) -> int:
        """Backward compatibility for Gmail max results."""
        return self.gmail_max_results


def get_settings(config_file: Optional[str] = None) -> Settings:
    """
    Get settings instance, optionally loaded from a config file.

    Args:
        config_file: Path to a JSON configuration file (optional)

    Returns:
        Settings instance
    """
    if config_file is None:
        return Settings()

    # Override with config file if provided
    if config_file and os.path.exists(config_file):
        with open(config_file, "r") as f:
            file_config = json.load(f)
            settings = Settings.model_validate(file_config)
    else:
        settings = Settings()

    return settings


# Create a default settings instance
settings = get_settings()
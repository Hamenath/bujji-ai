from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = Field(default="Personal Agentic AI Assistant")
    APP_VERSION: str = Field(default="0.5.1")
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    API_V1_PREFIX: str = Field(default="/api/v1")
    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=8000)
    DATABASE_URL: str = Field(default="sqlite:///./data/assistant.db")
    LOG_LEVEL: str = Field(default="INFO")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3.2")
    
    # Phase 3: Conversation & Context Configuration
    MAX_CONTEXT_MESSAGES: int = Field(default=20)
    MAX_CONTEXT_CHARS: int = Field(default=12000)
    CONVERSATION_TITLE_MAX_LENGTH: int = Field(default=60)
    WEBSOCKET_MAX_MESSAGE_CHARS: int = Field(default=10000)

    # Phase 4: Agent & Limits Configuration
    AGENT_MAX_STEPS: int = Field(default=8)
    AGENT_MAX_RETRIES_PER_STEP: int = Field(default=2)
    AGENT_TOOL_TIMEOUT_SECONDS: int = Field(default=30)
    AGENT_ROUTER_PARSE_RETRIES: int = Field(default=1)
    AGENT_PLANNER_PARSE_RETRIES: int = Field(default=1)
    AGENT_MAX_DUPLICATE_ACTIONS: int = Field(default=1)

    # Phase 5A: Web Search & Safe Reading Configuration
    WEB_SEARCH_MAX_RESULTS: int = Field(default=10)
    WEB_FETCH_TIMEOUT_SECONDS: int = Field(default=15)
    WEB_FETCH_MAX_BYTES: int = Field(default=2097152)  # 2MB
    WEB_FETCH_MAX_REDIRECTS: int = Field(default=5)
    WEB_READER_MAX_CHARS: int = Field(default=20000)
    WEB_MAX_PAGES_PER_RUN: int = Field(default=3)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

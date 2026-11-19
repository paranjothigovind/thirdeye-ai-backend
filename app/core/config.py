"""Application configuration"""
import json
from typing import List, Literal, Optional
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # Validation errors must never echo configuration values (they include secrets)
        hide_input_in_errors=True,
    )

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_ENDPOINT_CHAT: str
    AZURE_OPENAI_CHAT_API_KEY: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_CHAT_DEPLOYMENT: str
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT: str
    CORS_ORIGINS: list[str] = ["http://localhost", "https://thirdeye-ai-frontend.onrender.com"]

    # LLM generation provider (embeddings always use Azure OpenAI)
    LLM_PROVIDER: Literal["azure_openai", "anthropic"] = "azure_openai"
    # Prior user/assistant turns forwarded to the model (0 disables history)
    LLM_MAX_HISTORY_MESSAGES: int = Field(default=10, ge=0)

    # Anthropic Claude (only required when LLM_PROVIDER=anthropic)
    ANTHROPIC_API_KEY: Optional[SecretStr] = None
    ANTHROPIC_MODEL: str = "claude-opus-5-5"
    ANTHROPIC_MAX_TOKENS: int = Field(default=16000, ge=1)
    ANTHROPIC_TIMEOUT: float = Field(default=120.0, gt=0)
    ANTHROPIC_MAX_RETRIES: int = Field(default=2, ge=0)
    # low | medium | high | xhigh | max; empty string omits the parameter
    ANTHROPIC_EFFORT: str = "medium"
    # Server-side refusal fallback (beta): re-runs a declined request on a fallback model
    ANTHROPIC_REFUSAL_FALLBACK: bool = True

    # Public chat request limits (requests over a limit get HTTP 422)
    CHAT_MAX_MESSAGES: int = Field(default=40, ge=1)
    CHAT_MAX_MESSAGE_CHARS: int = Field(default=4000, ge=1)
    CHAT_MAX_TOTAL_CHARS: int = Field(default=24000, ge=1)

    # Usage limits for LLM endpoints (HTTP 429 when exceeded; 0 disables a limit)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_IP_PER_MINUTE: int = Field(default=20, ge=0)
    RATE_LIMIT_SESSION_PER_HOUR: int = Field(default=120, ge=0)
    SESSION_DAILY_TOKEN_LIMIT: int = Field(default=300000, ge=0)
    # Total LLM tokens (input + output) per UTC day across all users; 0 = unlimited.
    # Default sized for a small MVP: one chat uses roughly 3,500-4,500 tokens, so
    # 1,000,000 is about 220-280 chats per day. Raise it deliberately as usage grows.
    LLM_DAILY_TOKEN_BUDGET: int = Field(default=1_000_000, ge=0)
    # Number of trusted reverse proxies in front of the app. 0 ignores X-Forwarded-For.
    TRUSTED_PROXY_HOPS: int = Field(default=0, ge=0)
    # memory (per process) or redis (shared across instances, uses REDIS_URL)
    USAGE_STORE: Literal["memory", "redis"] = "memory"

    # Seconds between SSE keep-alive comments while a response is buffered (0 disables)
    SSE_KEEPALIVE_SECONDS: float = Field(default=15.0, ge=0)

    # Region-specific emergency policy (JSON). Empty = generic guidance, no phone numbers.
    EMERGENCY_POLICY_FILE: str = ""

    # Razorpay (test-mode keys until launch). Secrets are server-only; the mobile app
    # receives only the public key id.
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: Optional[SecretStr] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[SecretStr] = None

    # Azure AI Search
    AZURE_SEARCH_ENDPOINT: str
    AZURE_SEARCH_KEY: str
    AZURE_SEARCH_INDEX: str = "thirdeye-knowledge-index-v2"
    # Auto-repair recreates the index when schema drift (e.g. a non-filterable
    # `context`) is detected. Destructive - existing documents must be re-uploaded.
    AZURE_SEARCH_AUTO_REPAIR: bool = False

    # Azure Blob Storage
    AZURE_BLOB_CONNECTION_STRING: str
    AZURE_BLOB_CONTAINER: str = "third-eye-pdfs"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LangSmith
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "third-eye-chatbot"

    # Application
    APP_ENV: str = "development"
    CORS_ORIGINS: List[str] = ["https://happy-mud-017545400.1.azurestaticapps.net", "https://thirdeye-ai-frontend.onrender.com", "http://localhost:3000", "http://localhost:8000"]
    MAX_UPLOAD_SIZE_MB: int = 25

    # Database
    DATABASE_URL: str = "sqlite:///./thirdeye.db"

    # Authentication
    # Required: no built-in fallback. Generate with:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # RAG Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    TOP_K_RESULTS: int = 6
    EMBEDDING_DIMENSIONS: int = 3072

    # Web Scraping
    WEB_SCRAPING_RPS: float = 2.0

    @field_validator('SECRET_KEY', 'JWT_SECRET_KEY')
    @classmethod
    def validate_signing_secret(cls, v, info):
        value = (v or "").strip()
        if len(value) < 32 or value.lower().startswith(("change-me", "your-")):
            raise ValueError(
                f"{info.field_name} must be a random secret of at least 32 characters "
                "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
            )
        return value

    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return ["https://happy-mud-017545400.1.azurestaticapps.net", "https://thirdeye-ai-frontend.onrender.com", "http://localhost:3000", "http://localhost:8000"]
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v

    @field_validator('LLM_PROVIDER', mode='before')
    @classmethod
    def normalize_llm_provider(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator('ANTHROPIC_EFFORT', mode='before')
    @classmethod
    def validate_anthropic_effort(cls, v):
        value = (v or "").strip().lower()
        allowed = {"", "low", "medium", "high", "xhigh", "max"}
        if value not in allowed:
            raise ValueError(f"ANTHROPIC_EFFORT must be one of {sorted(allowed - {''})} or empty")
        return value

    @model_validator(mode='after')
    def validate_llm_provider_credentials(self):
        if self.LLM_PROVIDER == "anthropic":
            key = self.ANTHROPIC_API_KEY.get_secret_value().strip() if self.ANTHROPIC_API_KEY else ""
            if not key:
                raise ValueError(
                    "LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set. "
                    "Set ANTHROPIC_API_KEY or use LLM_PROVIDER=azure_openai."
                )
        return self

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        """Convert MB to bytes"""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()

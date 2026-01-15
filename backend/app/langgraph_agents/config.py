"""
MedSafe LangGraph Configuration

PATTERN: Centralized configuration with type safety (PDF pg 27-31)
SKILLS: @api-design-principles, @fastapi-templates, @ultrathink

Configures:
- Ollama qwen3:8b model integration
- PostgreSQL checkpointing for HITL
- Agent Ops & Observability settings
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
import os


class LangGraphSettings(BaseSettings):
    """
    Configuration for LangGraph Multi-Agent System

    SKILL: @fastapi-templates - Pydantic settings pattern
    SKILL: @ultrathink - Clear, typed configuration
    """

    # ========================================================================
    # OLLAMA MODEL CONFIGURATION (qwen3:8b)
    # ========================================================================
    # SKILL: @debugging-strategies - Use environment variables for Docker compatibility
    # SKILL: @python-performance-optimization - Increased timeouts for GPU processing
    ollama_base_url: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")  # Docker service name
    # Cloud is OPT-IN: only used when OLLAMA_CLOUD is set (non-empty) AND an API key is provided.
    # Default is local-only to avoid accidental cloud spend.
    ollama_model: str = os.getenv("OLLAMA_CLOUD", "").strip() or os.getenv("OLLAMA_LLM", "qwen3:8b")
    ollama_local_model: str = os.getenv("OLLAMA_LLM", "qwen3:8b")  # Local model (also fallback)
    ollama_api_key: Optional[str] = os.getenv("OLLAMA_API_KEY", None)  # API key for cloud models
    ollama_temperature: float = 0.1  # Low temp for medical accuracy
    ollama_max_tokens: int = 2048
    ollama_timeout: int = 300  # 5 minutes for complex multi-agent analysis
    
    @property
    def is_cloud_model(self) -> bool:
        """Check if using a cloud model (from OLLAMA_CLOUD env)"""
        # Cloud model only if explicitly set (non-empty).
        return bool(os.getenv("OLLAMA_CLOUD", "").strip())

    @property
    def effective_ollama_url(self) -> str:
        """
        Get the effective Ollama URL.

        For cloud models: https://ollama.com (ChatOllama adds /api automatically)
        For local models: http://ollama:11434 (local Ollama server)
        """
        if self.is_cloud_model and self.ollama_api_key:
            return "https://ollama.com"
        return self.ollama_base_url

    @property
    def effective_model_name(self) -> str:
        """
        Get the effective model name for API calls.

        For cloud models: Remove :latest suffix, use base name
        Example: "gemini-3-pro-preview:latest" -> "gemini-3-pro-preview"
        """
        model = self.ollama_model
        # Remove :latest suffix for cloud API
        if self.is_cloud_model and model.endswith(":latest"):
            return model.replace(":latest", "")
        return model

    # ========================================================================
    # POSTGRESQL CHECKPOINTING (HITL Pattern - PDF pg 22, 32)
    # ========================================================================
    # SKILL: @debugging-strategies - Use environment variables for Docker compatibility
    postgres_host: str = os.getenv("POSTGRES_HOST", "db")  # 'db' for Docker, 'localhost' for local
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "medsafe")
    postgres_user: str = os.getenv("POSTGRES_USER", "medsafe")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")

    @property
    def postgres_url(self) -> str:
        """PostgreSQL connection URL for checkpointing"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ========================================================================
    # AGENT BEHAVIOR SETTINGS (PDF pg 25-26)
    # ========================================================================
    max_reflection_cycles: int = 3  # Iterative refinement limit
    reflection_confidence_threshold: float = 0.85  # When to stop refining

    # Safety Guardrails (PDF pg 34-38)
    enable_safety_guardrails: bool = True
    block_on_critical_violations: bool = True

    # HITL Configuration
    # HITL is off by default because the current checkpointer is MemorySaver (non-persistent).
    # Enable only when you accept in-memory state or when persistent checkpointing is implemented.
    enable_hitl: bool = False
    hitl_timeout_seconds: int = 300  # 5 minutes for human review
    auto_escalate_critical: bool = True  # Always escalate CRITICAL risks

    # ========================================================================
    # RAG CONFIGURATION (PDF pg 21)
    # ========================================================================
    vector_store_enabled: bool = True
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:0.6b")  # Ollama embedding model
    top_k_documents: int = 5  # Number of evidence documents to retrieve
    similarity_threshold: float = 0.7

    # ========================================================================
    # OBSERVABILITY & AGENT OPS (PDF pg 27-31)
    # ========================================================================
    enable_tracing: bool = True
    enable_metrics: bool = True
    log_level: str = "INFO"
    trace_sample_rate: float = 1.0  # 100% sampling for medical app

    # Performance thresholds
    # SKILL: @python-performance-optimization - Adjusted for GPU-accelerated processing
    max_agent_execution_time: int = 600  # 10 minutes (complex multi-agent workflows)
    warning_execution_time: int = 120  # 2 minutes

    # ========================================================================
    # DATA PATHS
    # ========================================================================
    @property
    def project_root(self) -> Path:
        """Get project root directory"""
        return Path(__file__).parent.parent.parent.parent

    @property
    def data_dir(self) -> Path:
        """Data directory for CSV databases"""
        return self.project_root / "data"

    @property
    def drug_interactions_db(self) -> Path:
        """Path to drug interactions database"""
        return self.data_dir / "db_drug_interactions.csv"

    @property
    def medical_knowledge_dir(self) -> Path:
        """Directory for medical knowledge base (RAG)"""
        return self.data_dir / "medical_knowledge"

    class Config:
        env_file = ".env"
        env_prefix = "MEDSAFE_"
        case_sensitive = False
        # The repository uses a shared `.env` with many non-LangGraph keys.
        # In tests (and dev), we must ignore unrelated settings instead of failing validation.
        extra = "ignore"


# Global settings instance
_settings: Optional[LangGraphSettings] = None


def get_settings() -> LangGraphSettings:
    """
    Get global settings instance (singleton pattern)

    SKILL: @api-design-principles - Dependency injection ready
    """
    global _settings
    if _settings is None:
        _settings = LangGraphSettings()
    return _settings


def reset_settings():
    """Reset settings (useful for testing)"""
    global _settings
    _settings = None

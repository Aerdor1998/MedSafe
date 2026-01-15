"""
PostgreSQL Checkpointing for LangGraph HITL Pattern

PATTERN: State persistence for Human-in-the-Loop workflows (PDF pg 22, 32)
SKILLS: @ultrathink, @api-design-principles, @debugging-strategies

WHY CHECKPOINTING?
- Allows interrupting agent workflows for human review
- Persists state so workflow can resume after approval
- Critical for medical applications requiring physician oversight

ARCHITECTURE:
1. State saved to PostgreSQL before HITL interruption
2. Human reviews and provides feedback
3. State restored and workflow continues with human input

DURABILITY:
- PostgresSaver persists state to database
- Survives API/worker restarts
- Required for production HITL workflows
"""

import os
import logging
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)


class PostgresCheckpointManager:
    """
    Manages durable PostgreSQL checkpointing for LangGraph workflows.
    
    PATTERN: Interrupt Pattern for HITL (PDF pg 22, 32)
    SKILL: @api-design-principles - Clean checkpoint abstraction
    
    Provides durable state persistence that survives restarts.
    Falls back to MemorySaver only if PostgreSQL is unavailable.
    """

    def __init__(self):
        self._checkpointer: Optional[BaseCheckpointSaver] = None
        self._connection_string: Optional[str] = None
        self._is_durable: bool = False

    def _get_connection_string(self) -> Optional[str]:
        """Build PostgreSQL connection string from environment."""
        # Try DATABASE_URL first
        database_url = os.getenv("DATABASE_URL")
        if database_url and "postgresql" in database_url:
            return database_url
        
        # Build from individual components
        host = os.getenv("POSTGRES_HOST", "db")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "medsafe")
        user = os.getenv("POSTGRES_USER", "medsafe")
        password = os.getenv("POSTGRES_PASSWORD", "")
        
        if password and "CHANGE_ME" not in password:
            return f"postgresql://{user}:{password}@{host}:{port}/{db}"
        
        return None

    def initialize(self, connection_string: Optional[str] = None) -> None:
        """
        Initialize checkpointer with PostgreSQL persistence.
        
        Args:
            connection_string: PostgreSQL connection string (uses env if not provided)
        """
        self._connection_string = connection_string or self._get_connection_string()
        
        if self._connection_string:
            self._init_postgres_checkpointer()
        else:
            self._init_memory_fallback()

    def _init_postgres_checkpointer(self) -> None:
        """Initialize PostgresSaver for durable checkpointing."""
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            import psycopg
            
            logger.info("Initializing PostgreSQL checkpointing...")
            
            # Create a persistent connection with autocommit for checkpoint operations
            conn = psycopg.connect(self._connection_string, autocommit=True)
            
            # Create PostgresSaver with connection
            self._checkpointer = PostgresSaver(conn)
            
            # Setup tables (creates checkpoint tables if not exist)
            try:
                self._checkpointer.setup()
                logger.info("PostgreSQL checkpoint tables ready")
            except Exception as setup_error:
                logger.warning(f"Could not setup checkpoint tables (may already exist): {setup_error}")
            
            self._is_durable = True
            logger.info("✅ PostgreSQL checkpointing initialized (DURABLE)")
            
        except ImportError as e:
            logger.warning(
                f"langgraph-checkpoint-postgres or psycopg not installed: {e}. "
                "Install with: pip install langgraph-checkpoint-postgres psycopg"
            )
            self._init_memory_fallback()
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL checkpointing: {e}")
            logger.warning("Falling back to in-memory checkpointing")
            self._init_memory_fallback()

    def _init_memory_fallback(self) -> None:
        """Initialize MemorySaver as fallback (not durable)."""
        logger.warning("⚠️ Using MemorySaver (NOT DURABLE - state lost on restart)")
        logger.warning("   For production HITL, configure PostgreSQL checkpointing.")
        self._checkpointer = MemorySaver()
        self._is_durable = False

    @property
    def checkpointer(self) -> BaseCheckpointSaver:
        """
        Get checkpointer instance (lazy initialization).
        
        PATTERN: Singleton with lazy loading
        """
        if self._checkpointer is None:
            self.initialize()
        return self._checkpointer

    @property
    def is_durable(self) -> bool:
        """Check if checkpointer is using durable storage."""
        if self._checkpointer is None:
            self.initialize()
        return self._is_durable

    def close(self) -> None:
        """Close checkpointer and release resources."""
        if self._checkpointer is not None:
            # PostgresSaver may have connection to close
            if hasattr(self._checkpointer, "conn") and self._checkpointer.conn:
                try:
                    self._checkpointer.conn.close()
                except Exception:
                    pass
        self._checkpointer = None
        self._is_durable = False
        logger.info("Checkpointer closed")


class AsyncPostgresCheckpointManager:
    """
    Async-compatible PostgreSQL checkpointing for LangGraph.
    
    Uses AsyncPostgresSaver for async graph execution (ainvoke).
    Provides the same durability as sync version.
    """

    def __init__(self):
        self._checkpointer: Optional[BaseCheckpointSaver] = None
        self._connection_string: Optional[str] = None
        self._is_durable: bool = False
        self._pool = None

    def _get_connection_string(self) -> Optional[str]:
        """Build PostgreSQL connection string from environment."""
        database_url = os.getenv("DATABASE_URL")
        if database_url and "postgresql" in database_url:
            return database_url
        
        host = os.getenv("POSTGRES_HOST", "db")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "medsafe")
        user = os.getenv("POSTGRES_USER", "medsafe")
        password = os.getenv("POSTGRES_PASSWORD", "")
        
        if password and "CHANGE_ME" not in password:
            return f"postgresql://{user}:{password}@{host}:{port}/{db}"
        
        return None

    async def initialize(self, connection_string: Optional[str] = None) -> None:
        """
        Initialize async checkpointer with PostgreSQL persistence.
        
        Args:
            connection_string: PostgreSQL connection string
        """
        self._connection_string = connection_string or self._get_connection_string()
        
        if self._connection_string:
            await self._init_async_postgres()
        else:
            self._init_memory_fallback()

    async def _init_async_postgres(self) -> None:
        """Initialize AsyncPostgresSaver for async workflows."""
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool
            
            logger.info("Initializing async PostgreSQL checkpointing...")
            
            # Create async connection pool
            self._pool = AsyncConnectionPool(
                conninfo=self._connection_string,
                min_size=1,
                max_size=10,
                open=False,
            )
            await self._pool.open()
            
            # Create async checkpointer
            self._checkpointer = AsyncPostgresSaver(self._pool)
            
            # Setup tables
            try:
                await self._checkpointer.setup()
                logger.info("PostgreSQL checkpoint tables ready (async)")
            except Exception as setup_error:
                logger.warning(f"Could not setup checkpoint tables: {setup_error}")
            
            self._is_durable = True
            logger.info("✅ Async PostgreSQL checkpointing initialized (DURABLE)")
            
        except ImportError as e:
            logger.warning(f"Async checkpoint dependencies not available: {e}")
            logger.warning("Install with: pip install langgraph-checkpoint-postgres psycopg[pool]")
            self._init_memory_fallback()
        except Exception as e:
            logger.error(f"Failed to initialize async PostgreSQL checkpointing: {e}")
            self._init_memory_fallback()

    def _init_memory_fallback(self) -> None:
        """Initialize MemorySaver as fallback."""
        logger.warning("⚠️ Using MemorySaver (NOT DURABLE)")
        self._checkpointer = MemorySaver()
        self._is_durable = False

    @property
    def checkpointer(self) -> BaseCheckpointSaver:
        """Get checkpointer (must call initialize() first for async)."""
        if self._checkpointer is None:
            # Sync fallback for property access
            self._init_memory_fallback()
        return self._checkpointer

    @property
    def is_durable(self) -> bool:
        """Check if using durable storage."""
        return self._is_durable

    async def close(self) -> None:
        """Close async checkpointer and pool."""
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:
                pass
        self._checkpointer = None
        self._pool = None
        self._is_durable = False
        logger.info("Async checkpointer closed")


# =============================================================================
# Global instances and factory functions
# =============================================================================

_sync_checkpointer: Optional[PostgresCheckpointManager] = None
_async_checkpointer: Optional[AsyncPostgresCheckpointManager] = None


def get_checkpointer() -> PostgresCheckpointManager:
    """
    Get global sync checkpointer instance (singleton).
    
    For sync graph execution using invoke().
    """
    global _sync_checkpointer
    if _sync_checkpointer is None:
        _sync_checkpointer = PostgresCheckpointManager()
    return _sync_checkpointer


async def get_async_checkpointer() -> AsyncPostgresCheckpointManager:
    """
    Get global async checkpointer instance (singleton).
    
    For async graph execution using ainvoke().
    Must be called within async context.
    """
    global _async_checkpointer
    if _async_checkpointer is None:
        _async_checkpointer = AsyncPostgresCheckpointManager()
        await _async_checkpointer.initialize()
    return _async_checkpointer


def reset_checkpointer() -> None:
    """Reset sync checkpointer (useful for testing)."""
    global _sync_checkpointer
    if _sync_checkpointer:
        _sync_checkpointer.close()
    _sync_checkpointer = None


async def reset_async_checkpointer() -> None:
    """Reset async checkpointer (useful for testing)."""
    global _async_checkpointer
    if _async_checkpointer:
        await _async_checkpointer.close()
    _async_checkpointer = None


# =============================================================================
# Backwards compatibility
# =============================================================================

# Alias for backwards compatibility with existing code
MedSafeCheckpointer = PostgresCheckpointManager


__all__ = [
    "PostgresCheckpointManager",
    "AsyncPostgresCheckpointManager",
    "MedSafeCheckpointer",
    "get_checkpointer",
    "get_async_checkpointer",
    "reset_checkpointer",
    "reset_async_checkpointer",
]

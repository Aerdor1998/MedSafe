"""
Sistema de Logging Estruturado e em Tempo Real para MedSafe

SKILL: @debugging-strategies - Comprehensive logging for observability
PATTERN: Structured logging with real-time progress tracking

Fornece:
- Logs coloridos e estruturados
- Rastreamento de progresso de agentes em tempo real
- Contexto completo para debugging
- Métricas de performance
"""

import json
import logging
import sys
from datetime import datetime
from enum import Enum
from typing import Optional


class LogLevel(str, Enum):
    """Níveis de log customizados"""

    AGENT_START = "AGENT_START"
    AGENT_END = "AGENT_END"
    AGENT_PROGRESS = "AGENT_PROGRESS"
    AGENT_ERROR = "AGENT_ERROR"
    API_REQUEST = "API_REQUEST"
    API_RESPONSE = "API_RESPONSE"
    LLM_CALL = "LLM_CALL"
    LLM_RESPONSE = "LLM_RESPONSE"
    DB_QUERY = "DB_QUERY"


class ColoredFormatter(logging.Formatter):
    """
    Formatter com cores para terminal

    SKILL: @ultrathink - Clean, readable logging output
    """

    # Cores ANSI
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
        # Cores customizadas para agentes
        "AGENT_START": "\033[94m",  # Blue
        "AGENT_END": "\033[92m",  # Bright green
        "AGENT_PROGRESS": "\033[96m",  # Bright cyan
        "AGENT_ERROR": "\033[91m",  # Bright red
        "LLM_CALL": "\033[95m",  # Magenta
    }

    # Emojis para tipos de log
    EMOJIS = {
        "AGENT_START": "🤖",
        "AGENT_END": "",
        "AGENT_PROGRESS": "⚙️",
        "AGENT_ERROR": "",
        "API_REQUEST": "📥",
        "API_RESPONSE": "📤",
        "LLM_CALL": "🧠",
        "LLM_RESPONSE": "💬",
        "DB_QUERY": "",
        "DEBUG": "",
        "INFO": "ℹ️",
        "WARNING": "",
        "ERROR": "🚨",
        "CRITICAL": "💥",
    }

    def format(self, record):
        """Formatar log com cores e estrutura"""

        # Obter cor baseado no nível
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Obter emoji
        emoji = self.EMOJIS.get(record.levelname, "")

        # Timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]

        # Nome do módulo/agente
        module = record.name.split(".")[-1] if "." in record.name else record.name

        # Mensagem
        message = record.getMessage()

        # Montar log formatado
        log_parts = [
            f"{color}{emoji}",
            f"[{timestamp}]",
            f"[{record.levelname}]",
            f"[{module}]",
            f"{reset}{message}",
        ]

        # Adicionar informações extras se disponíveis
        if hasattr(record, "extra_data"):
            extra_str = json.dumps(record.extra_data, indent=2, ensure_ascii=False)
            log_parts.append(f"\n{color}  └─ Data: {reset}{extra_str}")

        if hasattr(record, "duration"):
            log_parts.append(f"{color}  └─ Duration: {reset}{record.duration:.2f}s")

        if hasattr(record, "agent_name"):
            log_parts.append(f"{color}  └─ Agent: {reset}{record.agent_name}")

        # Adicionar traceback se houver exceção
        if record.exc_info and record.exc_info is not True:
            log_parts.append(f"\n{color}  └─ Exception:{reset}")
            log_parts.append(self.formatException(record.exc_info))

        return " ".join(log_parts)


class AgentLogger:
    """
    Logger especializado para rastreamento de agentes

    PATTERN: Context manager for agent execution tracking
    SKILL: @debugging-strategies - Comprehensive agent observability
    """

    def __init__(self, agent_name: str, logger: logging.Logger):
        self.agent_name = agent_name
        self.logger = logger
        self.start_time = None
        self.step_count = 0

    def start(self, message: str, **kwargs):
        """Log início do agente"""
        self.start_time = datetime.now()
        self.step_count = 0

        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(start)",
            0,
            f"{self.agent_name} STARTED: {message}",
            (),
            None,
        )
        record.levelname = "AGENT_START"
        record.agent_name = self.agent_name

        if kwargs:
            record.extra_data = kwargs

        self.logger.handle(record)

    def progress(self, message: str, **kwargs):
        """Log progresso do agente"""
        self.step_count += 1

        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(progress)",
            0,
            f"  ⚙️  {self.agent_name} [Step {self.step_count}]: {message}",
            (),
            None,
        )
        record.levelname = "AGENT_PROGRESS"
        record.agent_name = self.agent_name

        if kwargs:
            record.extra_data = kwargs

        self.logger.handle(record)

    def llm_call(self, prompt_preview: str, **kwargs):
        """Log chamada ao LLM"""
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(llm)",
            0,
            f"  🧠 {self.agent_name} calling LLM: {prompt_preview[:80]}...",
            (),
            None,
        )
        record.levelname = "LLM_CALL"
        record.agent_name = self.agent_name

        if kwargs:
            record.extra_data = kwargs

        self.logger.handle(record)

    def llm_response(self, response_preview: str, duration: float, **kwargs):
        """Log resposta do LLM"""
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(llm_response)",
            0,
            f"  💬 {self.agent_name} LLM responded: {response_preview[:80]}...",
            (),
            None,
        )
        record.levelname = "LLM_RESPONSE"
        record.agent_name = self.agent_name
        record.duration = duration

        if kwargs:
            record.extra_data = kwargs

        self.logger.handle(record)

    def end(self, message: str, success: bool = True, **kwargs):
        """Log fim do agente"""
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
        else:
            duration = 0.0

        status = "COMPLETED" if success else "FAILED"

        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(end)",
            0,
            f"{'' if success else ''} {self.agent_name} {status}: {message}",
            (),
            None,
        )
        record.levelname = "AGENT_END" if success else "AGENT_ERROR"
        record.agent_name = self.agent_name
        record.duration = duration

        if kwargs:
            record.extra_data = kwargs

        self.logger.handle(record)

    def error(self, message: str, exc_info=None, **kwargs):
        """Log erro do agente"""
        record = self.logger.makeRecord(
            self.logger.name,
            logging.ERROR,
            "(error)",
            0,
            f"{self.agent_name} ERROR: {message}",
            (),
            exc_info,
        )
        record.levelname = "AGENT_ERROR"
        record.agent_name = self.agent_name

        if kwargs:
            record.extra_data = kwargs

        self.logger.handle(record)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_redaction: bool = True,
):
    """
    Configurar sistema de logging estruturado

    SKILL: @debugging-strategies - Centralized logging configuration
    SKILL: @ultrathink - Graceful degradation para ambientes Docker
    SECURITY: PHI/PII redaction integrada para LGPD compliance

    Args:
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Arquivo para salvar logs (opcional, None desabilita)
        enable_redaction: Se True, ativa redação de dados sensíveis (PHI/PII)

    Design Principles:
    - Docker-first: stdout/stderr sempre habilitado
    - Graceful: Continua funcionando se não conseguir criar arquivo
    - Configurável: Via environment ou parâmetros
    - LGPD-compliant: Redação automática de dados sensíveis em produção
    """
    import os

    # Determinar se deve habilitar redação (sempre em produção)
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
    should_redact = enable_redaction or is_production

    # Criar logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remover handlers existentes
    root_logger.handlers.clear()

    # Remover filtros existentes
    root_logger.filters.clear()

    # Handler para console com cores (SEMPRE habilitado)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(ColoredFormatter())

    # SECURITY: Adicionar filtro de redação de PHI/PII
    if should_redact:
        try:
            from .log_redaction import PHIRedactionFilter

            redaction_filter = PHIRedactionFilter(enabled=True)
            console_handler.addFilter(redaction_filter)
            root_logger.addFilter(redaction_filter)
        except ImportError:
            root_logger.warning(
                "PHIRedactionFilter não disponível - logs podem conter PHI"
            )

    root_logger.addHandler(console_handler)

    # Handler para arquivo (OPCIONAL - com tratamento de erros)
    if log_file:
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

            # Criar handler de arquivo
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)  # Arquivo captura tudo

            # Formato sem cores para arquivo
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)

            # SECURITY: Adicionar filtro de redação também ao arquivo
            if should_redact:
                try:
                    from .log_redaction import PHIRedactionFilter

                    file_handler.addFilter(PHIRedactionFilter(enabled=True))
                except ImportError:
                    pass

            root_logger.addHandler(file_handler)

            root_logger.info(f"File logging habilitado: {log_file}")

        except (PermissionError, OSError) as e:
            # Se falhar, apenas avisar e continuar com console
            root_logger.warning(
                f" Não foi possível criar arquivo de log '{log_file}': {e}"
            )
            root_logger.warning("   Continuando apenas com console logging (stdout)")

    # Reduzir verbosidade de bibliotecas externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    return root_logger


def get_agent_logger(agent_name: str) -> AgentLogger:
    """
    Obter logger especializado para um agente

    Args:
        agent_name: Nome do agente (ex: "TriageAgent")

    Returns:
        AgentLogger configurado
    """
    logger = logging.getLogger(f"medsafe.agents.{agent_name}")
    return AgentLogger(agent_name, logger)


def log_api_request(method: str, path: str, **kwargs):
    """Log requisição API"""
    logger = logging.getLogger("medsafe.api")

    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "(api_request)",
        0,
        f"📥 API Request: {method} {path}",
        (),
        None,
    )
    record.levelname = "API_REQUEST"

    if kwargs:
        record.extra_data = kwargs

    logger.handle(record)


def log_api_response(
    method: str, path: str, status_code: int, duration: float, **kwargs
):
    """Log resposta API"""
    logger = logging.getLogger("medsafe.api")

    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "(api_response)",
        0,
        f"📤 API Response: {method} {path} → {status_code}",
        (),
        None,
    )
    record.levelname = "API_RESPONSE"
    record.duration = duration

    if kwargs:
        record.extra_data = kwargs

    logger.handle(record)

"""
Unit tests for logging configuration

Tests AgentLogger, setup_logging, and log functions.
"""

import logging


class TestLogLevel:
    """Tests for LogLevel enum"""

    def test_log_level_values(self):
        """Test LogLevel enum has expected values"""
        from backend.app.utils.logging_config import LogLevel

        # Custom log levels for agent tracking
        assert hasattr(LogLevel, "AGENT_START")
        assert hasattr(LogLevel, "AGENT_END")
        assert hasattr(LogLevel, "AGENT_PROGRESS")
        assert hasattr(LogLevel, "LLM_CALL")


class TestAgentLogger:
    """Tests for AgentLogger class"""

    def test_agent_logger_init(self):
        """Test AgentLogger initialization"""
        from backend.app.utils.logging_config import AgentLogger

        base_logger = logging.getLogger("test_agent")
        logger = AgentLogger("TestAgent", base_logger)

        assert logger is not None
        assert logger.agent_name == "TestAgent"

    def test_agent_logger_start(self):
        """Test AgentLogger start method"""
        from backend.app.utils.logging_config import AgentLogger

        base_logger = logging.getLogger("test_agent_start")
        logger = AgentLogger("TestAgent", base_logger)

        # Should not raise
        logger.start("Starting operation", key="value")

    def test_agent_logger_end(self):
        """Test AgentLogger end method"""
        from backend.app.utils.logging_config import AgentLogger

        base_logger = logging.getLogger("test_agent_end")
        logger = AgentLogger("TestAgent", base_logger)
        logger.start("Starting")

        # Should not raise
        logger.end("Ending operation", success=True)

    def test_agent_logger_progress(self):
        """Test AgentLogger progress method"""
        from backend.app.utils.logging_config import AgentLogger

        base_logger = logging.getLogger("test_agent_progress")
        logger = AgentLogger("TestAgent", base_logger)

        # Should not raise
        logger.progress("Processing step 1", step=1, total=5)

    def test_agent_logger_error(self):
        """Test AgentLogger error method"""
        from backend.app.utils.logging_config import AgentLogger

        base_logger = logging.getLogger("test_agent_error")
        logger = AgentLogger("TestAgent", base_logger)

        # Should not raise
        logger.error("An error occurred", error_code="E001")

    def test_agent_logger_llm_call(self):
        """Test AgentLogger llm_call method"""
        from backend.app.utils.logging_config import AgentLogger

        base_logger = logging.getLogger("test_agent_llm")
        logger = AgentLogger("TestAgent", base_logger)

        # Should not raise
        logger.llm_call("Test prompt", model="test-model", temperature=0.7)

    def test_agent_logger_llm_response(self):
        """Test AgentLogger llm_response method"""
        from backend.app.utils.logging_config import AgentLogger

        base_logger = logging.getLogger("test_agent_llm_resp")
        logger = AgentLogger("TestAgent", base_logger)

        # Should not raise
        logger.llm_response("Test response", duration=1.5, tokens=100, chars=500)


class TestGetAgentLogger:
    """Tests for get_agent_logger function"""

    def test_get_agent_logger_returns_logger(self):
        """Test get_agent_logger returns AgentLogger"""
        from backend.app.utils.logging_config import AgentLogger, get_agent_logger

        logger = get_agent_logger("TestAgent")

        assert isinstance(logger, AgentLogger)

    def test_get_agent_logger_name(self):
        """Test get_agent_logger sets correct name"""
        from backend.app.utils.logging_config import get_agent_logger

        logger = get_agent_logger("MyAgent")

        assert logger.agent_name == "MyAgent"


class TestSetupLogging:
    """Tests for setup_logging function"""

    def test_setup_logging_default(self):
        """Test setup_logging with defaults"""
        from backend.app.utils.logging_config import setup_logging

        # Should not raise
        setup_logging()

    def test_setup_logging_with_level(self):
        """Test setup_logging with custom level"""
        from backend.app.utils.logging_config import setup_logging

        # Should not raise
        setup_logging(log_level="DEBUG")

    def test_setup_logging_with_file(self):
        """Test setup_logging with log file"""
        import os
        import tempfile

        from backend.app.utils.logging_config import setup_logging

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_file = f.name

        try:
            setup_logging(log_level="INFO", log_file=log_file)
        finally:
            # Reconfigurar fecha o FileHandler antes da remoção no Windows.
            setup_logging(log_level="INFO")
            if os.path.exists(log_file):
                os.unlink(log_file)


class TestLogAPIFunctions:
    """Tests for API logging functions"""

    def test_log_api_request(self):
        """Test log_api_request function"""
        from backend.app.utils.logging_config import log_api_request

        # Should not raise
        log_api_request(method="POST", path="/api/v2/analyze", client_ip="127.0.0.1")

    def test_log_api_response(self):
        """Test log_api_response function"""
        from backend.app.utils.logging_config import log_api_response

        # Should not raise
        log_api_response(
            method="POST", path="/api/v2/analyze", status_code=200, duration=0.5
        )


class TestColoredFormatter:
    """Tests for ColoredFormatter class"""

    def test_colored_formatter_init(self):
        """Test ColoredFormatter initialization"""
        from backend.app.utils.logging_config import ColoredFormatter

        formatter = ColoredFormatter()

        assert formatter is not None

    def test_colored_formatter_format(self):
        """Test ColoredFormatter format method"""
        from backend.app.utils.logging_config import ColoredFormatter

        formatter = ColoredFormatter()

        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Test message" in result

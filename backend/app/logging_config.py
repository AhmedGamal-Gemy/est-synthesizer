"""EST Synthesizer — Production logging configuration.

Uses structlog for structured logging with PositionalArgumentsFormatter
for native loggers and custom processors for foreign (stdlib) loggers.
JSON output in production and colored console output during development.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "console",
    log_file: str | None = None,
) -> None:
    """Configure structlog and standard library logging.

    All existing ``logging.getLogger(__name__)`` calls will be captured
    by structlog.  ``PositionalArgumentsFormatter`` is used for native
    structlog loggers; foreign (stdlib) loggers use a separate pre-chain
    without it to avoid the ``msg % args`` TypeError when
    ``ProcessorFormatter`` already formats the message via
    ``record.getMessage()``.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        log_format: ``"console"`` for colored human-readable output
            (recommended for development), ``"json"`` for structured JSON
            (recommended for production).
        log_file: Optional path to a log file.  When set, all log entries
            are also written to the file in JSON format.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # ── Shared processors (applied to all output channels) ─────────────
    shared_processors: list[structlog.typing.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # ── Foreign pre-chain (for stdlib loggers — no PositionalArgumentsFormatter) ─
    foreign_pre_chain_processors: list[structlog.typing.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer: structlog.typing.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # ── Configure structlog ────────────────────────────────────────────
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ── Build a ProcessorFormatter that stdlib loggers will use ────────
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=foreign_pre_chain_processors,
    )

    # ── Root handler (console) ─────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Remove default handlers to avoid duplicate output
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # ── Optional file handler (JSON format) ────────────────────────────
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
                foreign_pre_chain=foreign_pre_chain_processors,
            ),
        )
        root_logger.addHandler(file_handler)

    # ── Let uvicorn.access propagate to root logger ────────────────────
    # Without this, access logs stay in uvicorn's own handler, never
    # reaching the file handler or structlog formatting on the root.
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = True

    # ── Suppress overly verbose third-party loggers ────────────────────
    for noisy in ("httpx", "httpcore", "urllib3", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.get_logger("backend").info(
        "Logging configured",
        log_level=log_level,
        log_format=log_format,
        log_file=log_file,
    )




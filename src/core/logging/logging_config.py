import logging
import sys

_REQUEST_CONTEXT_FIELDS = ("request_id", "user_id", "order_id")


class _RequestContextFilter(logging.Filter):
    """Ensures request-correlation fields are always present on log records.

    Handlers/loggers may attach ``request_id``, ``user_id``, ``order_id`` via
    ``extra={...}``; this filter fills in blanks so the formatter never
    raises a ``KeyError`` when a field wasn't supplied.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for field in _REQUEST_CONTEXT_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, "-")
        return True


def configure_logging(log_level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestContextFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt=(
                "%(asctime)s | %(levelname)-8s | %(name)s | "
                "request_id=%(request_id)s user_id=%(user_id)s order_id=%(order_id)s | "
                "%(message)s"
            )
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())
    root_logger.handlers = [handler]

    # Quiet noisy third-party loggers unless we're in debug.
    for noisy_logger in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy_logger).setLevel(
            log_level.upper() if log_level.upper() == "DEBUG" else "WARNING"
        )

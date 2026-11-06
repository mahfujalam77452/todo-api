"""Request id for log lines.

The id lives in a context variable set by RequestLoggingMiddleware; a log
record factory copies it onto every record, so *any* log line written while a
request is handled (including tracebacks from "api.errors") carries it.
"""
import contextvars
import logging

request_id_var = contextvars.ContextVar("request_id", default="-")


def install_record_factory():
    previous = logging.getLogRecordFactory()
    if getattr(previous, "_adds_request_id", False):
        return  # already installed (ready() can run more than once in tests)

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.request_id = request_id_var.get()
        return record

    factory._adds_request_id = True
    logging.setLogRecordFactory(factory)


class OnlyWithTraceback(logging.Filter):
    """Pass only records that carry an exception.

    Django logs a line for *every* 4xx/5xx response, after our middleware has
    finished. For errors DRF already handled that is a duplicate without a
    traceback or request id; for crashes outside DRF it has the traceback.
    """

    def filter(self, record):
        return record.exc_info is not None

class RateLimited(logging.Filter):
    """Let one record through every `seconds`, drop the rest.

    During a Redis outage every request would otherwise log a traceback, twice.
    """

    def __init__(self, seconds=60):
        super().__init__()
        self.seconds = seconds
        self._last = None

    def filter(self, record):
        now = time.monotonic()
        if self._last is None or now - self._last >= self.seconds:
            self._last = now
            return True
        return False
import json
import logging
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone


request_id = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """Allowlisted metadata only: never log bodies, headers, query strings or locals."""

    def format(self, record):
        data = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            # Third-party error messages can contain credentials or request data.
            "event": record.getMessage() if record.name.startswith("petcare.") else "framework_log",
            "request_id": request_id.get(),
        }
        for name in ("method", "route", "status", "duration_ms", "resource", "resource_id"):
            if hasattr(record, name):
                data[name] = getattr(record, name)
        if record.exc_info and record.exc_info[0]:
            data["error_type"] = record.exc_info[0].__name__
            data["traceback"] = [
                {"file": frame.filename, "line": frame.lineno, "function": frame.name}
                for frame in traceback.extract_tb(record.exc_info[2])
            ]
        return json.dumps(data, ensure_ascii=False)

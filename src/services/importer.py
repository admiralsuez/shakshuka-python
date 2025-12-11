"""Task import helpers.

This module parses CSV and TXT task files into a common in-memory
representation so that the API layer in ``task_routes`` stays thin.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Tuple, Optional, Any
import csv
import io
import logging

logger = logging.getLogger(__name__)

SanitizeFn = Optional[Callable[[Any], Any]]


def _maybe_sanitize(value: Any, sanitize: SanitizeFn) -> Any:
    """Apply the provided sanitize function if present.

    ``sanitize`` is expected to be compatible with the function injected
    into ``task_routes`` (it may accept either a dict or a string).
    """

    if sanitize is None:
        return value
    try:
        return sanitize(value)
    except Exception:  # pragma: no cover - defensive only
        logger.warning("sanitize_input failed, returning original value", exc_info=True)
        return value


def parse_csv_tasks(content: str, sanitize_input: SanitizeFn = None) -> Tuple[List[Dict], List[str]]:
    """Parse CSV task content.

    Expected columns (case-sensitive):
    ``title``, ``description``, ``project``, ``duration``, ``due_date``, ``priority``.
    Unknown columns are ignored.

    Returns a tuple of (tasks, errors).
    """

    tasks: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        csv_file = io.StringIO(content)
        reader = csv.DictReader(csv_file)

        for row_num, row in enumerate(reader, start=2):  # header is row 1
            try:
                row = _maybe_sanitize(row, sanitize_input)

                title = (row.get("title", "") or "").strip()
                if not title:
                    errors.append(f"Row {row_num}: Title is required")
                    continue

                description = (row.get("description", "") or "").strip()
                project = (row.get("project", "") or "").strip()

                # duration
                duration_str = (row.get("duration", "60") or "").strip()
                try:
                    duration = int(duration_str) if duration_str else 60
                except ValueError:
                    duration = 60

                # due date – accept ISO or common YYYY-MM-DD / MM/DD/YYYY
                due_date = (row.get("due_date", "") or "").strip()
                if due_date:
                    if not _is_valid_date(due_date):
                        errors.append(f"Row {row_num}: Invalid date format for '{due_date}'")
                        due_date = None

                # priority
                priority = (row.get("priority", "medium") or "").strip().lower()
                if priority not in {"low", "medium", "high"}:
                    priority = "medium"

                tasks.append(
                    {
                        "title": title,
                        "description": description,
                        "project": project,
                        "estimated_duration": duration,
                        "due_date": due_date,
                        "priority": priority,
                    }
                )

            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"Row {row_num}: {exc}")

    except Exception as exc:  # file-level error
        errors.append(f"CSV parsing error: {exc}")

    return tasks, errors


def parse_txt_tasks(content: str, sanitize_input: SanitizeFn = None) -> Tuple[List[Dict], List[str]]:
    """Parse TXT task content.

    Format per line (``|`` separated):
    ``Title | Description | Project | Duration | Due Date``.

    Returns a tuple of (tasks, errors).
    """

    tasks: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        lines = content.strip().split("\n")

        for line_num, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                line = _maybe_sanitize(line, sanitize_input)

                parts = [part.strip() for part in str(line).split("|")]
                if len(parts) < 1:
                    errors.append(f"Line {line_num}: At least title is required")
                    continue

                title = parts[0]
                if not title:
                    errors.append(f"Line {line_num}: Title is required")
                    continue

                description = parts[1] if len(parts) > 1 else ""
                project = parts[2] if len(parts) > 2 else ""

                # duration
                duration = 60
                if len(parts) > 3 and parts[3]:
                    try:
                        duration = int(parts[3])
                    except ValueError:
                        errors.append(f"Line {line_num}: Invalid duration '{parts[3]}'")

                # due date
                due_date = None
                if len(parts) > 4 and parts[4]:
                    candidate = parts[4]
                    if _is_valid_date(candidate):
                        due_date = candidate
                    else:
                        errors.append(f"Line {line_num}: Invalid date format '{candidate}'")

                tasks.append(
                    {
                        "title": title,
                        "description": description,
                        "project": project,
                        "estimated_duration": duration,
                        "due_date": due_date,
                        "priority": "medium",
                    }
                )

            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"Line {line_num}: {exc}")

    except Exception as exc:
        errors.append(f"TXT parsing error: {exc}")

    return tasks, errors


def _is_valid_date(value: str) -> bool:
    """Return True if the string can be parsed as a date we accept.

    Accepted formats:
    - ISO 8601 ``YYYY-MM-DD`` or ``YYYY-MM-DDTHH:MM:SS``
    - ``YYYY-MM-DD``
    - ``MM/DD/YYYY``
    """

    if not value:
        return False

    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False

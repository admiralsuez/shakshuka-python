from __future__ import annotations

import logging
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from contextvars import Token
from typing import Iterator, Optional


_correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='-')

_CORRELATION_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def normalize_correlation_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:  # noqa: broad-except - defensive: accept any string conversion failure
            return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 64:
        return None
    if not _CORRELATION_ID_RE.match(value):
        return None
    return value


def get_correlation_id() -> str:
    return _correlation_id_var.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> Token[str]:
    value = correlation_id or new_correlation_id()
    return _correlation_id_var.set(value)


def reset_correlation_id(token: Token[str]) -> None:
    _correlation_id_var.reset(token)


def init_logging_context() -> None:
    old_factory = logging.getLogRecordFactory()

    if getattr(old_factory, '_shakshuka_correlation_wrapped', False):
        return

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        try:
            record.correlation_id = get_correlation_id()
        except Exception:  # noqa: broad-except - defensive: log factory must never fail
            record.correlation_id = '-'
        return record

    setattr(record_factory, '_shakshuka_correlation_wrapped', True)
    logging.setLogRecordFactory(record_factory)


def init_flask_middleware(app, *, header_name: str = 'X-Request-ID') -> None:
    from flask import g, request

    @app.before_request
    def _set_request_correlation_id():
        incoming = normalize_correlation_id(
            request.headers.get(header_name)
            or request.headers.get('X-Correlation-ID')
        )
        token = set_correlation_id(incoming)
        g._correlation_id_token = token

    @app.after_request
    def _attach_request_correlation_id(response):
        try:
            response.headers[header_name] = get_correlation_id()
        except Exception:  # noqa: broad-except - Flask middleware must never crash response
            logging.getLogger(__name__).exception('Failed to attach correlation id to response')
        return response

    @app.teardown_request
    def _clear_request_correlation_id(_exc=None):
        try:
            token = getattr(g, '_correlation_id_token', None)
            if token is not None:
                reset_correlation_id(token)
        except Exception:  # noqa: broad-except - Flask teardown must never crash
            logging.getLogger(__name__).exception('Failed to reset correlation id')


@contextmanager
def correlation_context(correlation_id: Optional[str] = None) -> Iterator[str]:
    token = set_correlation_id(correlation_id)
    try:
        yield get_correlation_id()
    finally:
        reset_correlation_id(token)

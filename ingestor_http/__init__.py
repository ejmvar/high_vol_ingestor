"""HTTP transport adapter for the telemetry ingestion port."""

from .server import create_http_server

__all__ = ["create_http_server"]

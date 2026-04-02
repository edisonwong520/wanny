import logging
import os
from threading import Lock

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


_INIT_LOCK = Lock()
_INITIALIZED = False


class TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        context = span.get_span_context() if span else None
        if context and context.is_valid:
            record.trace_id = f"{context.trace_id:032x}"
            record.span_id = f"{context.span_id:016x}"
        else:
            record.trace_id = "-"
            record.span_id = "-"
        return True


def get_tracer(name: str):
    return trace.get_tracer(name)


def initialize_telemetry() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return

    with _INIT_LOCK:
        if _INITIALIZED:
            return

        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": os.getenv("OTEL_SERVICE_NAME", "wanny-backend"),
                    "service.version": os.getenv("OTEL_SERVICE_VERSION", "0.1.0"),
                    "deployment.environment": os.getenv("OTEL_ENVIRONMENT", "development"),
                }
            )
        )

        exporters = {
            item.strip().lower()
            for item in os.getenv("OTEL_TRACES_EXPORTER", "").split(",")
            if item.strip()
        }

        if "console" in exporters:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        if "otlp" in exporters:
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            headers = {}
            raw_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
            for item in raw_headers.split(","):
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                if key.strip():
                    headers[key.strip()] = value.strip()

            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=headers or None,
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _INITIALIZED = True

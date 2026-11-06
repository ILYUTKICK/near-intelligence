"""Scheduled refresh adapters (NI-030). Importing this package performs no I/O.

Every adapter here is an explicitly invoked operator CLI; nothing in the
application starts or schedules one automatically (DATA_PIPELINE.md:
``INGESTION_ENABLED`` defaults to false and the effective source allowlist
starts empty).
"""

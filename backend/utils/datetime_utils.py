"""Datetime utilities for timezone-aware operations"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Get current UTC datetime (timezone-aware)"""
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """Get current UTC datetime without timezone info for database compatibility"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
from datetime import datetime, timezone


def utc_isoformat(value):
    """Serialize database timestamps as unambiguous ISO 8601 UTC values."""
    if value is None:
        return None
    if not isinstance(value, datetime):
        return str(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

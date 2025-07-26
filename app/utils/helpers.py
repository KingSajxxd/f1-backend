# /app/utils/helpers.py
import collections.abc
from datetime import datetime
import json

class DateTimeEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle datetime objects.
    """
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def deep_merge(destination, source):
    """
    Recursively merges source dictionary into destination dictionary.
    - If a key exists in both and both values are dictionaries, it merges them.
    - If a key exists in both and the destination value is a list, the source overwrites it.
    - Otherwise, the value from the source is set in the destination.
    """
    for key, value in source.items():
        if key in destination and isinstance(destination[key], dict) and isinstance(value, dict):
            # If both are dictionaries, recurse
            deep_merge(destination[key], value)
        else:
            # Otherwise, just overwrite the destination value with the source value
            destination[key] = value
    return destination

def safe_to_float(value: str) -> float | None:
    """
    Safely converts a string value to a float.
    Handles strings with '+' signs.
    Returns None if conversion is not possible (e.g., for "LAP 2").
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        # float() can handle strings with a leading '+' sign
        return float(value)
    except (ValueError, TypeError):
        # Return None if the string is not a valid float (e.g., "LAP 2")
        return None
    
def time_string_to_seconds(time_str: str) -> float | None:
    """
    Converts a time string like "1:44.634" or "44.634" to total seconds.
    Returns None if the format is invalid.
    """
    if not isinstance(time_str, str) or not time_str:
        return None
    
    try:
        if ':' in time_str:
            parts = time_str.split(':')
            minutes = int(parts[0])
            seconds = float(parts[1])
            return (minutes * 60) + seconds
        else:
            return float(time_str)
    except (ValueError, TypeError, IndexError):
        return None
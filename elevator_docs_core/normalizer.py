"""
Variable name normalizer for Elevator Documentation Automation.

Normalizes variable names from Excel ($-prefixed) and templates to a consistent format.
Preserves Czech diacritics and original casing.
"""

import logging

logger = logging.getLogger(__name__)


def normalize_variable_name(raw_name):
    """Normalize a variable name by stripping $, whitespace, and replacing internal spaces.

    Args:
        raw_name: Raw variable name (e.g., "$misto_instalace", "$ druh_model_vyrobku")

    Returns:
        Normalized variable name (e.g., "misto_instalace", "druh_model_vyrobku").
        Returns empty string for None, empty, or whitespace-only inputs.
    """
    if raw_name is None:
        return ""

    name = str(raw_name).strip()

    if not name:
        return ""

    # Remove $ prefix (handles "$var", "$ var", "$  var")
    if name.startswith("$"):
        name = name[1:]

    # Strip whitespace after $ removal
    name = name.strip()

    # Replace any remaining internal spaces with underscore
    name = "_".join(name.split())

    # Convert to lowercase for case-insensitive matching
    name = name.lower()

    return name


def normalize_dict_keys(data):
    """Apply normalize_variable_name to all keys in a dictionary.

    Args:
        data: Dictionary with potentially un-normalized keys.

    Returns:
        New dictionary with normalized keys. If key normalization causes duplicates,
        the last value wins and a warning is logged.
    """
    result = {}
    for key, value in data.items():
        normalized = normalize_variable_name(key)
        if not normalized:
            logger.warning("Skipping entry with empty key (original: %r)", key)
            continue
        if normalized in result:
            logger.warning(
                "Duplicate key after normalization: %r and %r both normalize to %r",
                key, [k for k, v in data.items() if normalize_variable_name(k) == normalized][0],
                normalized,
            )
        result[normalized] = value
    return result

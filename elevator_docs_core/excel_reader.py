"""
Excel reader module for Elevator Documentation Automation.

Reads order data from zakazka.xlsx and business rules from Pravidla.xlsx.
Handles data type coercion, variable name normalization, and edge cases.
"""

import datetime
import logging

import pandas as pd

from elevator_docs_core.config import (
    PRAVIDLA_COLS,
    PRAVIDLA_SHEET_NAME,
    SUPPORTED_OPERATORS,
    VALUE_COL,
    VARIABLE_COL,
    ZAKAZKA_SHEET_NAME,
)
from elevator_docs_core.normalizer import normalize_variable_name

logger = logging.getLogger(__name__)


def _coerce_value_to_string(value):
    """Convert any Excel cell value to a string suitable for template rendering.

    Handles: None/NaN -> "", datetime -> "DD.MM.YYYY", time -> "H:M",
    float whole numbers -> int string, everything else -> str().
    """
    if value is None:
        return ""

    if isinstance(value, float):
        # NaN check
        if pd.isna(value):
            return ""
        # Whole number floats -> int string (e.g., 1050.0 -> "1050")
        if value == int(value):
            return str(int(value))
        return str(value)

    if isinstance(value, datetime.datetime):
        return value.strftime("%d.%m.%Y")

    if isinstance(value, datetime.time):
        # time(2, 1) -> "2:1" (ratio string for lanovani etc.)
        return f"{value.hour}:{value.minute}"

    if isinstance(value, datetime.date):
        return value.strftime("%d.%m.%Y")

    if isinstance(value, int):
        return str(value)

    # For pandas NA types
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value)


def read_order_data(filepath):
    """Read order data variables from zakazka.xlsx.

    Args:
        filepath: Path to the zakazka.xlsx file.

    Returns:
        Dictionary mapping normalized variable names to string values.
        All values are strings. Missing/None values become empty strings.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the sheet is not found.
    """
    logger.info("Reading order data from: %s", filepath)

    # Read with openpyxl to preserve original types (don't use dtype=str)
    df = pd.read_excel(
        filepath,
        sheet_name=ZAKAZKA_SHEET_NAME,
        engine="openpyxl",
        header=None,  # No header row processing - we handle it manually
    )

    # Column B = index 1 (0-based), Column D = index 3 (0-based)
    col_b_idx = ord(VARIABLE_COL) - ord("A")  # 1
    col_d_idx = ord(VALUE_COL) - ord("A")  # 3

    result = {}
    skipped = 0

    for idx, row in df.iterrows():
        raw_name = row.iloc[col_b_idx] if col_b_idx < len(row) else None
        raw_value = row.iloc[col_d_idx] if col_d_idx < len(row) else None

        # Skip header row (row 0 in DataFrame = row 1 in Excel)
        if idx == 0:
            continue

        # Skip rows with no variable name
        if raw_name is None or (isinstance(raw_name, float) and pd.isna(raw_name)):
            skipped += 1
            continue

        raw_name_str = str(raw_name).strip()
        if not raw_name_str:
            skipped += 1
            continue

        # Normalize the variable name
        normalized_name = normalize_variable_name(raw_name_str)
        if not normalized_name:
            skipped += 1
            continue

        # Coerce value to string
        string_value = _coerce_value_to_string(raw_value)

        # Check for duplicates
        if normalized_name in result:
            logger.warning(
                "Duplicate variable '%s' at row %d (previous value: %r, new value: %r)",
                normalized_name, idx + 1, result[normalized_name], string_value,
            )

        result[normalized_name] = string_value

    logger.info(
        "Read %d variables from order data (%d rows skipped)",
        len(result), skipped,
    )

    return result


def read_rules(filepath):
    """Read business rules from Pravidla.xlsx.

    Args:
        filepath: Path to the Pravidla.xlsx file.

    Returns:
        List of rule dictionaries, each with keys:
        id, flag, variable, operator, value, text.
        Returns empty list if no rules found.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the sheet is not found.
    """
    logger.info("Reading rules from: %s", filepath)

    df = pd.read_excel(
        filepath,
        sheet_name=PRAVIDLA_SHEET_NAME,
        engine="openpyxl",
        header=None,
    )

    # Map column letters to 0-based indices
    col_indices = {}
    for field, col_letter in PRAVIDLA_COLS.items():
        col_indices[field] = ord(col_letter) - ord("A")

    rules = []

    for idx, row in df.iterrows():
        # Skip header row
        if idx == 0:
            continue

        # Read all fields
        rule = {}
        has_data = False
        for field, col_idx in col_indices.items():
            val = row.iloc[col_idx] if col_idx < len(row) else None
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                has_data = True
            rule[field] = val

        # Skip completely empty rows
        if not has_data:
            continue

        # Validate and clean rule fields
        rule_id = rule.get("id")
        if rule_id is not None:
            rule["id"] = int(rule_id) if isinstance(rule_id, (int, float)) else str(rule_id)

        # Normalize the variable name (strip $)
        raw_variable = rule.get("variable")
        if raw_variable is not None:
            rule["variable"] = normalize_variable_name(str(raw_variable))
        else:
            logger.warning("Rule %s has no variable name, skipping", rule_id)
            continue

        # Clean flag name
        flag = rule.get("flag")
        if flag is not None:
            rule["flag"] = str(flag).strip()
        else:
            logger.warning("Rule %s has no flag name, skipping", rule_id)
            continue

        # Validate and clean operator
        op = rule.get("operator")
        if op is not None:
            op = str(op).strip()
            if op not in SUPPORTED_OPERATORS:
                logger.warning(
                    "Rule %s has unsupported operator '%s', skipping", rule_id, op,
                )
                continue
            rule["operator"] = op
        else:
            logger.warning("Rule %s has no operator, skipping", rule_id)
            continue

        # Clean value (keep as-is for type coercion in rule engine)
        value = rule.get("value")
        if value is not None:
            rule["value"] = str(value).strip() if isinstance(value, str) else value
        else:
            logger.warning("Rule %s has no threshold value, skipping", rule_id)
            continue

        # Clean text
        text = rule.get("text")
        rule["text"] = str(text).strip() if text is not None else ""

        rules.append(rule)

    logger.info("Read %d rules", len(rules))
    return rules

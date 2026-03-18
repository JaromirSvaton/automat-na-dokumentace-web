"""
Context builder for Elevator Documentation Automation.

Merges order data and rule results into a single context dictionary
for use with docxtpl template rendering.
"""

import datetime
import logging

logger = logging.getLogger(__name__)


def build_context(order_data, rule_results):
    """Build a merged context dictionary for template rendering.

    Merges order data and rule engine results into a single dict.
    Adds automatic variables (datum, rok). Ensures all values are strings.

    Args:
        order_data: Dictionary from read_order_data() (variable_name -> value).
        rule_results: Dictionary from RuleEngine.evaluate() (flag_name -> value).

    Returns:
        Merged context dictionary with all values as strings.
        Rule results override order data on key conflicts.
    """
    context = {}

    # Start with order data
    for key, value in order_data.items():
        context[key] = _ensure_string(value)

    # Merge rule results (overrides order data on conflict)
    for key, value in rule_results.items():
        if key in context:
            logger.debug(
                "Rule result '%s' overrides order data value", key,
            )
        context[key] = _ensure_string(value)

    # Add automatic variables
    now = datetime.datetime.now()
    context["datum"] = now.strftime("%d.%m.%Y")
    context["rok"] = str(now.year)

    logger.info(
        "Built context with %d variables (%d order + %d rules + 2 auto)",
        len(context), len(order_data), len(rule_results),
    )

    return context


def _ensure_string(value):
    """Ensure a value is a string. Handles bool, None, etc."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return value
    return str(value)

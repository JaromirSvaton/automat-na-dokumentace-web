"""
Rule engine for Elevator Documentation Automation.

Evaluates business rules from Pravidla.xlsx against order data.
Uses Python's operator module for safe comparisons (no eval/exec).
"""

import logging
import operator

from elevator_docs_core.config import SUPPORTED_OPERATORS

logger = logging.getLogger(__name__)

# Map operator strings to operator module functions
OPERATOR_MAP = {
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


def _try_numeric(value):
    """Try to convert a value to a float for numeric comparison.

    Returns (float_value, True) if conversion succeeds, (original, False) if not.
    """
    if isinstance(value, (int, float)):
        return float(value), True
    if isinstance(value, str):
        try:
            return float(value.replace(",", ".").strip()), True
        except (ValueError, TypeError):
            return value, False
    return value, False


class RuleEngine:
    """Evaluates business rules against order data using safe operator comparisons."""

    def __init__(self, rules):
        """Initialize the rule engine with a list of rule dictionaries.

        Args:
            rules: List of rule dicts from read_rules(), each with keys:
                   id, flag, variable, operator, value, text.
        """
        self.rules = rules
        logger.info("RuleEngine initialized with %d rules", len(rules))

    def evaluate(self, order_data):
        """Evaluate all rules against the order data.

        Args:
            order_data: Dictionary of variable_name -> value from read_order_data().

        Returns:
            Dictionary of flag variables:
            - flag_name -> True/False (whether the rule condition was met)
            - flag_name_text -> string (text to use if condition was met, empty if not)
        """
        result = {}

        for rule in self.rules:
            rule_id = rule.get("id", "?")
            flag_name = rule.get("flag", "")
            variable_name = rule.get("variable", "")
            op_str = rule.get("operator", "")
            threshold = rule.get("value")
            text_if_true = rule.get("text", "")

            # Validate operator
            if op_str not in SUPPORTED_OPERATORS:
                logger.warning(
                    "Rule %s: unsupported operator '%s', skipping", rule_id, op_str,
                )
                continue

            op_func = OPERATOR_MAP.get(op_str)
            if op_func is None:
                logger.warning("Rule %s: no operator function for '%s'", rule_id, op_str)
                continue

            # Get variable value from order data
            if variable_name not in order_data:
                logger.warning(
                    "Rule %s: variable '%s' not found in order data, skipping",
                    rule_id, variable_name,
                )
                # Set defaults for missing variable
                result[flag_name] = False
                result[flag_name + "_text"] = ""
                continue

            var_value = order_data[variable_name]

            # Try numeric comparison first
            var_numeric, var_is_num = _try_numeric(var_value)
            threshold_numeric, threshold_is_num = _try_numeric(threshold)

            try:
                if var_is_num and threshold_is_num:
                    # Numeric comparison
                    condition_met = op_func(var_numeric, threshold_numeric)
                    logger.debug(
                        "Rule %s: %s (%s) %s %s (%s) -> %s",
                        rule_id, variable_name, var_numeric, op_str,
                        threshold, threshold_numeric, condition_met,
                    )
                else:
                    # Fall back to string comparison
                    condition_met = op_func(str(var_value), str(threshold))
                    logger.debug(
                        "Rule %s: '%s' %s '%s' (string) -> %s",
                        rule_id, var_value, op_str, threshold, condition_met,
                    )
            except Exception as e:
                logger.warning(
                    "Rule %s: comparison failed (%s), treating as False: %s",
                    rule_id, e, e,
                )
                condition_met = False

            if condition_met:
                result[flag_name] = True
                result[flag_name + "_text"] = text_if_true
                logger.info(
                    "Rule %s: condition MET -> %s = True", rule_id, flag_name,
                )
            else:
                result[flag_name] = False
                result[flag_name + "_text"] = ""
                logger.info(
                    "Rule %s: condition NOT met -> %s = False", rule_id, flag_name,
                )

        return result

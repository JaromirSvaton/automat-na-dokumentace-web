"""
Configuration module for Elevator Documentation Automation.

Contains all configuration constants, sheet names, column mappings,
and supported operators for the document generation pipeline.
"""

# ============================================================================
# EXCEL SHEET NAMES
# ============================================================================

# Order data sheet (zakazka.xlsx) - use index 0 for reliability across systems
ZAKAZKA_SHEET_INDEX = 0

# Rules data sheet (Pravidla.xlsx) - use index 0 for reliability across systems
PRAVIDLA_SHEET_INDEX = 0


# ============================================================================
# COLUMN MAPPINGS - Order Data (zakazka.xlsx)
# ============================================================================

# Column B: Variable names (with $ prefix)
VARIABLE_COL = "B"

# Column D: Variable values
VALUE_COL = "D"


# ============================================================================
# COLUMN MAPPINGS - Rules Data (Pravidla.xlsx)
# ============================================================================

# Columns C-H as discovered in analysis (A-B are empty)
PRAVIDLA_COLS = {
    "id": "C",          # Rule ID
    "flag": "D",        # Target flag name (Cilovy_flag)
    "variable": "E",    # Variable name to test (Promenna)
    "operator": "F",    # Comparison operator
    "value": "G",       # Threshold value (Hodnota)
    "text": "H",        # Text to set if rule is true (Text_If_True)
}


# ============================================================================
# DIRECTORY PATHS
# ============================================================================

# Original templates directory
TEMPLATES_DIR = "templates"

# Output directory for converted templates (Jinja2 syntax)
TEMPLATES_CONVERTED_DIR = "templates_converted"

# Output directory for generated documents
OUTPUT_DIR = "output"

# Logs directory
LOGS_DIR = "logs"


# ============================================================================
# RULE ENGINE - SUPPORTED OPERATORS
# ============================================================================

# Safe operators for rule evaluation (used with Python operator module)
SUPPORTED_OPERATORS = {"<", ">", "<=", ">=", "==", "!="}


# ============================================================================
# APPLICATION METADATA
# ============================================================================

APP_NAME = "Generátor dokumentace výtahů"
APP_VERSION = "1.0.0"

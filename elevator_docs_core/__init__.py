"""
Elevator Documentation Automation - Core Package.

A reusable Python package containing all core logic for generating
elevator documentation from Excel data and Word templates.
"""

from .config import APP_NAME, APP_VERSION
from .pipeline import run_pipeline

__version__ = APP_VERSION

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "run_pipeline",
]

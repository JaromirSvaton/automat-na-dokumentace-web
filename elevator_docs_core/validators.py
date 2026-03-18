"""
Template variable validator for Elevator Documentation Automation.

Cross-references variables expected by templates against the context dictionary.
Produces validation reports identifying missing and extra variables.
"""

import logging
import os

from docxtpl import DocxTemplate

logger = logging.getLogger(__name__)


def validate_template_variables(template_path, context):
    """Validate that a template's variables are satisfied by the context.

    Args:
        template_path: Path to a converted .docx template (Jinja2 syntax).
        context: Context dictionary (output of build_context()).

    Returns:
        Dictionary with validation report:
        {template_file, expected_vars, provided_vars, missing, extra}
    """
    report = {
        "template_file": template_path,
        "expected_vars": set(),
        "provided_vars": set(context.keys()),
        "missing": set(),
        "extra": set(),
    }

    try:
        doc = DocxTemplate(template_path)
        expected = doc.get_undeclared_template_variables()
        report["expected_vars"] = expected

        # Missing: template expects but context doesn't have
        report["missing"] = expected - set(context.keys())

        # Extra: context has but template doesn't use (informational only)
        report["extra"] = set(context.keys()) - expected

        if report["missing"]:
            logger.warning(
                "Template %s: missing %d variables: %s",
                os.path.basename(template_path),
                len(report["missing"]),
                sorted(report["missing"]),
            )
        else:
            logger.debug(
                "Template %s: all %d variables satisfied",
                os.path.basename(template_path),
                len(expected),
            )

    except Exception as e:
        logger.error(
            "Failed to validate %s: %s", template_path, e,
        )
        report["missing"] = set()
        report["extra"] = set()

    return report


def validate_all_templates(templates_dir, context):
    """Validate all templates in a directory against the context.

    Args:
        templates_dir: Directory with converted .docx templates.
        context: Context dictionary.

    Returns:
        List of validation report dictionaries.
    """
    reports = []

    for filename in sorted(os.listdir(templates_dir)):
        if not filename.endswith('.docx'):
            continue

        template_path = os.path.join(templates_dir, filename)
        report = validate_template_variables(template_path, context)
        reports.append(report)

    total_missing = sum(len(r["missing"]) for r in reports)
    logger.info(
        "Validated %d templates, %d total missing variables",
        len(reports), total_missing,
    )

    return reports

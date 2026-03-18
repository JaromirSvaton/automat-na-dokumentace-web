"""
Document generator for Elevator Documentation Automation.

Batch generates Word documents from converted templates using docxtpl.
Handles missing variables gracefully (empty string, not crash).
"""

import logging
import os

import jinja2
from docxtpl import DocxTemplate

from elevator_docs_core.validators import validate_template_variables

logger = logging.getLogger(__name__)


def generate_document(template_path, context, output_path):
    """Generate a single document from a converted template.

    Args:
        template_path: Path to a converted .docx template (Jinja2 syntax).
        context: Context dictionary with all variables as strings.
        output_path: Path where the generated document will be saved.

    Returns:
        Dictionary with generation result:
        {template, output_path, success, variables_used, warnings, error}
    """
    result = {
        "template": os.path.basename(template_path),
        "output_path": output_path,
        "success": False,
        "variables_used": 0,
        "warnings": [],
        "error": None,
    }

    try:
        # Validate first (warnings only, don't block)
        validation = validate_template_variables(template_path, context)
        if validation["missing"]:
            warning_msg = "Missing variables: {}".format(
                ", ".join(sorted(validation["missing"]))
            )
            result["warnings"].append(warning_msg)
            logger.warning(
                "%s: %s", os.path.basename(template_path), warning_msg,
            )

        result["variables_used"] = len(validation["expected_vars"])

        # Load and render template
        doc = DocxTemplate(template_path)

        # Use Jinja2 Undefined (silent) to replace missing vars with empty string
        jinja_env = jinja2.Environment(undefined=jinja2.Undefined)
        jinja_env.globals.update(jinja2.Environment().globals)

        doc.render(context, jinja_env)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        # Save the generated document
        doc.save(output_path)

        result["success"] = True
        logger.info(
            "Generated: %s (%d variables)",
            os.path.basename(output_path), result["variables_used"],
        )

    except Exception as e:
        result["error"] = str(e)
        logger.error(
            "Failed to generate %s: %s",
            os.path.basename(template_path), e,
        )

    return result


def generate_all_documents(templates_dir, context, output_dir):
    """Generate all documents from converted templates.

    Args:
        templates_dir: Directory with converted .docx templates.
        context: Context dictionary with all variables.
        output_dir: Directory where generated documents will be saved.

    Returns:
        List of generation result dictionaries.
    """
    os.makedirs(output_dir, exist_ok=True)

    results = []

    for filename in sorted(os.listdir(templates_dir)):
        if not filename.endswith('.docx'):
            continue

        template_path = os.path.join(templates_dir, filename)
        output_path = os.path.join(output_dir, filename)

        result = generate_document(template_path, context, output_path)
        results.append(result)

    success_count = len([r for r in results if r["success"]])
    total_count = len(results)

    logger.info(
        "Generated %d/%d documents", success_count, total_count,
    )

    return results

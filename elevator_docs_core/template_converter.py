"""
Template converter for Elevator Documentation Automation.

Converts $variable_name placeholders in .docx templates to Jinja2 {{ variable_name }}
syntax for use with docxtpl. Handles Word XML run-splitting where $ and variable name
are in separate <w:r> elements.
"""

import logging
import os
import re
import zipfile
from io import BytesIO

from lxml import etree

from elevator_docs_core.config import TEMPLATES_DIR, TEMPLATES_CONVERTED_DIR
from elevator_docs_core.normalizer import normalize_variable_name

logger = logging.getLogger(__name__)

# Word XML namespace
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_T = f"{{{W_NS}}}t"
W_R = f"{{{W_NS}}}r"


def _find_dollar_variables_in_text(text):
    """Find all $variable_name patterns in a text string.

    Returns list of (match_start, match_end, variable_name) tuples.
    """
    dollar = chr(36)
    pattern = re.escape(dollar) + r'\s*([A-Za-z_\u00C0-\u024F][A-Za-z0-9_\u00C0-\u024F]*)'
    results = []
    for m in re.finditer(pattern, text):
        var_name = m.group(1)
        results.append((m.start(), m.end(), var_name))
    return results


def _process_xml_content(xml_bytes):
    """Process a Word XML file, converting $var to {{ var }}.

    Handles two cases:
    1. Inline: $variable_name entirely within one <w:t> element
    2. Split-run: $ in one <w:r> and variable_name in the next <w:r>

    Returns (modified_xml_bytes, list_of_converted_variables).
    """
    root = etree.fromstring(xml_bytes)
    converted_vars = []
    dollar = chr(36)

    # Pass 1: Handle split-run patterns ($ in one run, name in next)
    # We need to iterate through all runs in document order
    all_runs = list(root.iter(W_R))

    i = 0
    while i < len(all_runs):
        run = all_runs[i]
        t_elem = run.find(W_T)

        if t_elem is not None and t_elem.text is not None:
            text = t_elem.text

            # Check if this run ends with $ (possibly with trailing spaces)
            stripped = text.rstrip()
            if stripped.endswith(dollar):
                # Look ahead for the variable name in the next run(s)
                next_i = i + 1
                if next_i < len(all_runs):
                    next_run = all_runs[next_i]
                    next_t = next_run.find(W_T)

                    if next_t is not None and next_t.text is not None:
                        next_text = next_t.text
                        # Check if next run starts with a valid variable name
                        var_match = re.match(
                            r'([A-Za-z_\u00C0-\u024F][A-Za-z0-9_\u00C0-\u024F]*)(.*)',
                            next_text, re.DOTALL
                        )
                        if var_match:
                            var_name = var_match.group(1)
                            remainder = var_match.group(2)
                            normalized = normalize_variable_name(var_name)

                            # Check if the runs share the same parent
                            # (both in same paragraph or cell)
                            if run.getparent() is next_run.getparent():
                                # Replace $ in current run with {{ normalized_name }}
                                prefix = text[:len(stripped) - 1]  # everything before $
                                t_elem.text = prefix + "{{ " + normalized + " }}"
                                # Preserve xml:space
                                t_elem.set(
                                    '{http://www.w3.org/XML/1998/namespace}space',
                                    'preserve'
                                )

                                if remainder:
                                    # Next run has more text after variable name
                                    next_t.text = remainder
                                else:
                                    # Next run is now empty — remove it
                                    next_run.getparent().remove(next_run)
                                    all_runs.pop(next_i)

                                converted_vars.append(normalized)
                                logger.debug(
                                    "Split-run converted: %s%s -> {{ %s }}",
                                    dollar, var_name, normalized,
                                )
                                i += 1
                                continue

        i += 1

    # Pass 2: Handle inline patterns ($variable_name in single <w:t>)
    for t_elem in root.iter(W_T):
        if t_elem.text is None:
            continue

        text = t_elem.text
        matches = _find_dollar_variables_in_text(text)

        if not matches:
            continue

        # Replace from end to start to preserve positions
        new_text = text
        for start, end, var_name in reversed(matches):
            normalized = normalize_variable_name(var_name)
            new_text = new_text[:start] + "{{ " + normalized + " }}" + new_text[end:]
            if normalized not in converted_vars:
                converted_vars.append(normalized)
            logger.debug(
                "Inline converted: %s%s -> {{ %s }}", dollar, var_name, normalized,
            )

        t_elem.text = new_text
        t_elem.set(
            '{http://www.w3.org/XML/1998/namespace}space', 'preserve'
        )

    modified_xml = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    return modified_xml, converted_vars


def convert_template(input_path, output_path):
    """Convert a single .docx template from $var to {{ var }} syntax.

    Args:
        input_path: Path to the original .docx template.
        output_path: Path where the converted template will be saved.

    Returns:
        Dictionary with conversion report:
        {input_file, output_file, variables_found, variables_converted, errors}
    """
    report = {
        "input_file": input_path,
        "output_file": output_path,
        "variables_found": [],
        "variables_converted": 0,
        "errors": [],
    }

    try:
        # Read the docx as ZIP
        with zipfile.ZipFile(input_path, 'r') as zin:
            # Create output in memory first
            buffer = BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)

                    # Process XML files that may contain variables
                    if item.filename == 'word/document.xml' or \
                       item.filename.startswith('word/header') or \
                       item.filename.startswith('word/footer'):
                        try:
                            modified_data, found_vars = _process_xml_content(data)
                            report["variables_found"].extend(found_vars)
                            data = modified_data
                        except Exception as e:
                            logger.error(
                                "Error processing %s in %s: %s",
                                item.filename, input_path, e,
                            )
                            report["errors"].append(
                                f"Error processing {item.filename}: {e}"
                            )

                    zout.writestr(item, data)

        # Write the buffer to the output file
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(buffer.getvalue())

        report["variables_converted"] = len(report["variables_found"])
        logger.info(
            "Converted %s: %d variables found",
            os.path.basename(input_path), report["variables_converted"],
        )

    except Exception as e:
        logger.error("Failed to convert %s: %s", input_path, e)
        report["errors"].append(str(e))

    return report


def convert_all_templates(input_dir=None, output_dir=None):
    """Convert all .docx templates in a directory from $var to {{ var }}.

    Args:
        input_dir: Directory with original templates (default: config.TEMPLATES_DIR).
        output_dir: Directory for converted templates (default: config.TEMPLATES_CONVERTED_DIR).

    Returns:
        List of conversion report dictionaries.
    """
    if input_dir is None:
        input_dir = TEMPLATES_DIR
    if output_dir is None:
        output_dir = TEMPLATES_CONVERTED_DIR

    os.makedirs(output_dir, exist_ok=True)

    reports = []

    for filename in sorted(os.listdir(input_dir)):
        input_path = os.path.join(input_dir, filename)

        # Skip .doc files (not supported)
        if filename.endswith('.doc') and not filename.endswith('.docx'):
            logger.warning(
                "Skipping .doc file (not supported, needs manual conversion): %s",
                filename,
            )
            continue

        # Process .docx files
        if filename.endswith('.docx'):
            output_path = os.path.join(output_dir, filename)
            report = convert_template(input_path, output_path)
            reports.append(report)

    converted_count = len([r for r in reports if not r.get("errors")])
    logger.info(
        "Converted %d/%d templates", converted_count, len(reports),
    )

    return reports

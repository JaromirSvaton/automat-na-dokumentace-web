"""
Generation report module for Elevator Documentation Automation.

Creates human-readable reports of the document generation process,
showing success/failure per template and missing variable warnings.
"""

import datetime
import logging
import os

logger = logging.getLogger(__name__)


def create_report(results, validation_reports=None, elapsed_seconds=None, logs_dir=None):
    """Create a plain text generation report.

    Args:
        results: List of generation result dicts from generate_all_documents().
        validation_reports: Optional list of validation report dicts.
        elapsed_seconds: Optional elapsed time in seconds.
        logs_dir: Directory to save the report file (default: config.LOGS_DIR).

    Returns:
        Report string (plain text, suitable for GUI log area and console).
    """
    from elevator_docs_core.config import LOGS_DIR

    if logs_dir is None:
        logs_dir = LOGS_DIR

    now = datetime.datetime.now()
    lines = []

    lines.append("=" * 50)
    lines.append("  REPORT GENEROVÁNÍ DOKUMENTŮ")
    lines.append("=" * 50)
    lines.append(f"Datum: {now.strftime('%d.%m.%Y %H:%M')}")
    lines.append("")

    success_count = len([r for r in results if r["success"]])
    total_count = len(results)
    lines.append(f"Vygenerováno: {success_count}/{total_count} dokumentů")
    if elapsed_seconds is not None:
        lines.append(f"Celkový čas: {elapsed_seconds:.1f} s")
    lines.append("")

    # Per-template results
    for r in results:
        template = r["template"]
        if r["success"]:
            vars_used = r.get("variables_used", 0)
            lines.append(f"  [OK] {template} ({vars_used} proměnných)")
        else:
            error = r.get("error", "neznámá chyba")
            lines.append(f"  [!!] {template} — CHYBA: {error}")

    # Warnings section
    warnings = []
    for r in results:
        for w in r.get("warnings", []):
            warnings.append(f"  - {r['template']}: {w}")

    if validation_reports:
        for v in validation_reports:
            if v.get("missing"):
                template = os.path.basename(v.get("template_file", "?"))
                missing_vars = ", ".join(sorted(v["missing"]))
                warnings.append(
                    f"  - {template}: chybí proměnné: {missing_vars}"
                )

    if warnings:
        lines.append("")
        lines.append("Varování:")
        for w in warnings:
            lines.append(w)

    lines.append("")
    lines.append("=" * 50)
    lines.append("  KONEC REPORTU")
    lines.append("=" * 50)

    report_text = "\n".join(lines)

    # Save report to logs directory
    try:
        os.makedirs(logs_dir, exist_ok=True)
        filename = f"generation_report_{now.strftime('%Y%m%d_%H%M')}.txt"
        filepath = os.path.join(logs_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info("Report saved to: %s", filepath)
    except Exception as e:
        logger.warning("Failed to save report to file: %s", e)

    return report_text

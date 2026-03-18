"""
Pipeline orchestrator for Elevator Documentation Automation.

Runs the full document generation pipeline: read data → evaluate rules →
build context → convert templates → validate → generate documents → report.
"""

import datetime
import logging
import os
import time

logger = logging.getLogger(__name__)


def run_pipeline(zakazka_path, pravidla_path, templates_dir, output_dir,
                 templates_converted_dir=None, logs_dir=None, log_callback=None):
    """Run the full document generation pipeline.

    This function orchestrates all pipeline steps.

    Args:
        zakazka_path: Path to zakazka.xlsx.
        pravidla_path: Path to Pravidla.xlsx.
        templates_dir: Path to the templates directory.
        output_dir: Path to the output directory.
        templates_converted_dir: Path for converted templates (default: templates_converted).
        logs_dir: Path for log files (default: logs).
        log_callback: Optional function(message) for progress logging.

    Returns:
        Dictionary with pipeline results:
        {success, generated_count, total_count, report_text, errors, output_folder}
    """
    from elevator_docs_core.config import TEMPLATES_CONVERTED_DIR, LOGS_DIR

    if templates_converted_dir is None:
        templates_converted_dir = TEMPLATES_CONVERTED_DIR
    if logs_dir is None:
        logs_dir = LOGS_DIR

    def log(msg):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    result = {
        "success": False,
        "generated_count": 0,
        "total_count": 0,
        "report_text": "",
        "errors": [],
    }

    try:
        start_time = time.time()

        # Step 1: Read order data
        log("Načítám data zakázky...")
        from elevator_docs_core.excel_reader import read_order_data
        order_data = read_order_data(zakazka_path)
        log(f"  Načteno {len(order_data)} proměnných")

        # Extract cislo_zakazky for output folder naming
        cislo_zakazky = order_data.get('cislo_zakazky', 'unknown')
        cislo_zakazky = str(cislo_zakazky).replace('/', '-').replace('\\', '-').replace(':', '-')

        # Step 2: Read rules
        log("Načítám pravidla...")
        from elevator_docs_core.excel_reader import read_rules
        rules = read_rules(pravidla_path)
        log(f"  Načteno {len(rules)} pravidel")

        # Step 3: Evaluate rules
        log("Vyhodnocuji pravidla...")
        from elevator_docs_core.rule_engine import RuleEngine
        engine = RuleEngine(rules)
        rule_results = engine.evaluate(order_data)
        flags_true = len([v for v in rule_results.values() if v is True])
        log(f"  Vyhodnoceno {len(rules)} pravidel ({flags_true} splněno)")

        # Step 4: Build context
        log("Sestavuji kontext...")
        from elevator_docs_core.context_builder import build_context
        context = build_context(order_data, rule_results)
        log(f"  Kontext obsahuje {len(context)} proměnných")

        # Step 5: Convert templates
        log("Konvertuji šablony...")
        from elevator_docs_core.template_converter import convert_all_templates
        conv_reports = convert_all_templates(templates_dir, templates_converted_dir)
        converted_count = len([r for r in conv_reports if not r.get("errors")])
        log(f"  Konvertováno {converted_count} šablon")

        # Step 6: Validate
        log("Validuji proměnné...")
        from elevator_docs_core.validators import validate_all_templates
        validation_reports = validate_all_templates(templates_converted_dir, context)
        total_missing = sum(len(r["missing"]) for r in validation_reports)
        if total_missing > 0:
            log(f"  Varování: {total_missing} chybějících proměnných")
        else:
            log("  Všechny proměnné jsou dostupné")

        # Step 7: Generate documents
        log("Generuji dokumenty...")
        from elevator_docs_core.doc_generator import generate_all_documents

        # Create timestamped output subfolder
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
        folder_name = f"{timestamp}_{cislo_zakazky}"
        generation_output_dir = os.path.join(output_dir, folder_name)
        os.makedirs(generation_output_dir, exist_ok=True)

        gen_results = generate_all_documents(templates_converted_dir, context, generation_output_dir)
        success_count = len([r for r in gen_results if r["success"]])
        total_count = len(gen_results)
        log(f"  Vygenerováno {success_count}/{total_count} dokumentů")

        # Step 8: Create report
        log("Vytvářím report...")
        from elevator_docs_core.report import create_report
        elapsed = time.time() - start_time
        report_text = create_report(
            gen_results, validation_reports,
            elapsed_seconds=elapsed, logs_dir=logs_dir
        )

        result["success"] = success_count == total_count
        result["generated_count"] = success_count
        result["total_count"] = total_count
        result["report_text"] = report_text
        result["output_folder"] = generation_output_dir

        log("")
        log(report_text)
        log("")
        log(f"Hotovo — {success_count}/{total_count} dokumentů vytvořeno ve složce: {generation_output_dir}")

    except FileNotFoundError as e:
        error_msg = f"Soubor nenalezen: {e}"
        log(f"[CHYBA] {error_msg}")
        result["errors"].append(error_msg)
    except ValueError as e:
        error_msg = f"Chyba dat: {e}"
        log(f"[CHYBA] {error_msg}")
        result["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Neočekávaná chyba: {e}"
        log(f"[CHYBA] {error_msg}")
        result["errors"].append(error_msg)
        logger.exception("Pipeline error")

    return result

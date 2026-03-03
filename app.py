"""
Streamlit web application for Elevator Documentation Automation.

A web-based UI for generating elevator documentation from Excel files
and Word templates. Designed with future cloud storage in mind.
"""

import io
import logging
import os
import tempfile
import zipfile

import streamlit as st
from streamlit_file_browser import st_file_browser
from elevator_docs_core import APP_NAME, APP_VERSION
from elevator_docs_core.config import TEMPLATES_DIR, OUTPUT_DIR, LOGS_DIR
from elevator_docs_core.pipeline import run_pipeline

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="📄",
    layout="wide",
)


def save_uploaded_file(uploaded_file, suffix=".xlsx"):
    """Save an uploaded file to a temporary file and return the path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return tmp.name


def zip_directory(folder_path):
    """Create a ZIP file from a directory."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zf.write(file_path, arcname)
    buffer.seek(0)
    return buffer


def folder_picker(key, label, default_path, help_text=None):
    """Folder picker using streamlit-file-browser."""
    
    if f"{key}_path" not in st.session_state:
        st.session_state[f"{key}_path"] = default_path
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_path = st.text_input(
            label,
            value=st.session_state[f"{key}_path"],
            help=help_text,
            key=f"{key}_text_input"
        )
        if new_path != st.session_state[f"{key}_path"]:
            st.session_state[f"{key}_path"] = new_path
    
    with col2:
        with st.expander("🌐 Procházet", expanded=False):
            fs_root = os.path.dirname(st.session_state[f"{key}_path"]) or "."
            selected = st_file_browser(
                fs_root,
                key=f"{key}_browser",
                show_choose_file=False,
                show_download_file=False,
                show_preview=False,
                show_new_folder=False,
                show_upload_file=False,
                show_delete_file=False,
            )
            if selected:
                selected_path = selected.get("fullPath")
                if selected_path and os.path.isdir(selected_path):
                    st.session_state[f"{key}_path"] = selected_path
                    st.rerun()
    
    return st.session_state[f"{key}_path"]


def main():
    st.title(f"{APP_NAME}")
    st.caption(f"verze {APP_VERSION}")

    st.markdown("---")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Vstupní soubory")
        
        zakazka_file = st.file_uploader(
            "Soubor zakázky (zakazka.xlsx)",
            type=["xlsx"],
            help="Excel soubor s proměnnými zakázky"
        )
        
        pravidla_file = st.file_uploader(
            "Soubor pravidel (Pravidla.xlsx)",
            type=["xlsx"],
            help="Excel soubor s business pravidly"
        )

    with col2:
        st.subheader("Nastavení")
        
        templates_dir = folder_picker(
            "templates",
            "Složka šablon",
            TEMPLATES_DIR,
            "Cesta ke složce s Word šablonami"
        )
        
        output_dir = folder_picker(
            "output",
            "Výstupní složka",
            OUTPUT_DIR,
            "Cesta pro vygenerované dokumenty"
        )

    st.markdown("---")

    if st.button("Generovat dokumenty", type="primary", disabled=not (zakazka_file and pravidla_file)):
        if not zakazka_file:
            st.error("Prosím nahrajte soubor zakázky.")
            return
        if not pravidla_file:
            st.error("Prosím nahrajte soubor pravidel.")
            return

        with st.spinner("Generuji dokumenty..."):
            progress_placeholder = st.empty()
            log_placeholder = st.empty()
            
            def log_callback(msg):
                log_placeholder.text(msg)
            
            try:
                progress_placeholder.info("Ukládám nahrané soubory...")
                
                zakazka_path = save_uploaded_file(zakazka_file)
                pravidla_path = save_uploaded_file(pravidla_file)
                
                progress_placeholder.info("Spouštím generování...")
                
                result = run_pipeline(
                    zakazka_path=zakazka_path,
                    pravidla_path=pravidla_path,
                    templates_dir=templates_dir,
                    output_dir=output_dir,
                    log_callback=log_callback,
                )
                
                os.unlink(zakazka_path)
                os.unlink(pravidla_path)
                
                progress_placeholder.empty()
                
                if result["success"]:
                    st.success(f"✅ Hotovo! Vygenerováno {result['generated_count']}/{result['total_count']} dokumentů")
                    
                    output_folder = result.get("output_folder", "")
                    if output_folder and os.path.exists(output_folder):
                        st.info(f"📁 Výstupní složka: `{output_folder}`")
                        
                        with st.spinner("Vytvářím ZIP archiv..."):
                            zip_buffer = zip_directory(output_folder)
                        
                        st.download_button(
                            label="📥 Stáhnout dokumenty jako ZIP",
                            data=zip_buffer,
                            file_name=f"dokumenty_{os.path.basename(output_folder)}.zip",
                            mime="application/zip",
                        )
                    else:
                        st.warning("Výstupní složka nebyla nalezena.")
                else:
                    st.error(f"❌ Generování selhalo")
                    if result.get("errors"):
                        for err in result["errors"]:
                            st.error(f"  Chyba: {err}")
                    
                    if result["generated_count"] > 0:
                        st.warning(f"⚠️ Částečně úspěšné: {result['generated_count']}/{result['total_count']} dokumentů")

                with st.expander("📋 Zobrazit report"):
                    st.text(result.get("report_text", ""))

            except Exception as e:
                progress_placeholder.empty()
                st.exception(f"Došlo k chybě: {e}")
                logger.exception("Web app error")

    st.markdown("---")
    st.markdown("""
    ### Jak to funguje
    1. Nahrajte **zakazka.xlsx** s proměnnými zakázky
    2. Nahrajte **Pravidla.xlsx** s business pravidly  
    3. Klepněte na **Generovat dokumenty**
    4. Stáhněte vygenerované dokumenty jako ZIP
    
    *Aplikace je navržena pro budoucí cloudové úložiště.*
    """)


if __name__ == "__main__":
    main()

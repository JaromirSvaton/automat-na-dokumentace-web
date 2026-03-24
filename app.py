"""
Streamlit web application for Elevator Documentation Automation.

A web-based UI for generating elevator documentation from Excel files
and Word templates. Supports local file upload and Google Drive integration.

Google login is optional — local upload works without it.
Google Drive features are available after logging in.
"""

import io
import logging
import os
import shutil
import tempfile
import zipfile

import streamlit as st
from elevator_docs_core import APP_NAME, APP_VERSION
from elevator_docs_core.pipeline import run_pipeline

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="📄",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def save_uploaded_file(uploaded_file, suffix=".xlsx"):
    """Save a Streamlit UploadedFile to a temp file, return the path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return tmp.name


def save_bytes_to_temp(data, filename):
    """Save raw bytes to a temp file preserving the original extension."""
    suffix = os.path.splitext(filename)[1] or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        return tmp.name


def zip_directory(folder_path):
    """Create an in-memory ZIP from *folder_path* and return a BytesIO."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(folder_path):
            for fname in files:
                full = os.path.join(root, fname)
                zf.write(full, os.path.relpath(full, folder_path))
    buffer.seek(0)
    return buffer


def cleanup_temp_dirs(*dirs):
    """Delete temporary directories after ZIP is downloaded.

    Removes directories safely (ignore_errors=True in case files are still open).
    Logs are kept - only templates, converted templates, and output are deleted.
    """
    for d in dirs:
        if d and os.path.exists(d):
            try:
                shutil.rmtree(d)
                logger.info(f"Cleaned up temp directory: {d}")
            except Exception as e:
                logger.warning(f"Failed to clean up {d}: {e}")


def cleanup_temp_file(path):
    """Delete a temporary file if it exists.
    
    Args:
        path: Path to the file to delete.
    """
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Cleaned up temp file: {path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {path}: {e}")


def _has_auth_config():
    """Return True if Google OAuth secrets are configured."""
    try:
        auth = st.secrets.get("auth", {})
        return bool(auth.get("client_id")) and bool(auth.get("client_secret"))
    except Exception:
        return False


def _is_logged_in():
    """Return True if a user is currently authenticated via st.login."""
    try:
        return st.user.is_logged_in
    except AttributeError:
        return False


def _get_access_token():
    """Return the OAuth access token or None."""
    try:
        return st.user.tokens.get("access")
    except (AttributeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Google Drive file browser (search + folder navigation)
# ---------------------------------------------------------------------------

def _drive_search_and_pick(service, key, label, mime_types, multiple=False):
    """Unified Drive file picker with search and folder browse.

    Provides two ways to find files:
    - **Search**: type a filename fragment, see matching results instantly
    - **Browse**: navigate folder tree (in an expander)

    Args:
        service: Drive v3 service object.
        key: Unique key for session state.
        label: UI label for the section.
        mime_types: List of MIME type strings to filter by.
        multiple: If True, allow selecting multiple files.

    Returns:
        list of (file_id, file_name) tuples, or empty list.
    """
    from drive_utils import (
        search_files, list_recent_files, list_files, list_folders,
        download_file, MIME_FOLDER,
    )

    session_key = f"drive_selected_{key}"
    if session_key not in st.session_state:
        st.session_state[session_key] = []  # list of {"id": ..., "name": ...}

    st.markdown(f"**{label}**")

    # --- Already selected files -------------------------------------------
    if st.session_state[session_key]:
        selected = st.session_state[session_key]
        names = ", ".join(f["name"] for f in selected)
        st.caption(f"Vybráno: {names}")
        if st.button("Zrušit výběr", key=f"clear_{key}"):
            st.session_state[session_key] = []
            st.rerun()
        return [(f["id"], f["name"]) for f in selected]

    # --- Search box -------------------------------------------------------
    search_query = st.text_input(
        "Hledat na Drive",
        placeholder="Zadejte název souboru...",
        key=f"search_{key}",
        label_visibility="collapsed",
    )

    if search_query and len(search_query) >= 2:
        try:
            with st.spinner("Hledám..."):
                results = search_files(service, search_query, mime_types=mime_types)
        except Exception as e:
            st.error(f"Chyba při hledání: {e}")
            results = []

        if results:
            _render_file_list(results, key, "search", multiple)
        else:
            st.caption("Žádné výsledky.")
    elif not search_query:
        # --- Show recent files when search is empty ----------------------
        try:
            recent = list_recent_files(service, mime_types=mime_types, page_size=8)
        except Exception:
            recent = []

        if recent:
            st.caption("Nedávné soubory:")
            _render_file_list(recent, key, "recent", multiple)

    # --- Folder browse (secondary) ----------------------------------------
    with st.expander("Procházet složky", expanded=False):
        nav_key = f"nav_{key}"
        if nav_key not in st.session_state:
            st.session_state[nav_key] = [{"id": "root", "name": "Disk"}]

        stack = st.session_state[nav_key]
        current = stack[-1]

        # Breadcrumb
        crumbs = " / ".join(item["name"] for item in stack)
        st.caption(f"📂 {crumbs}")

        # Go-up button
        if len(stack) > 1:
            if st.button("Nahoru", key=f"{nav_key}_up"):
                stack.pop()
                st.rerun()

        # List sub-folders
        try:
            folders = list_folders(service, parent_id=current["id"])
        except Exception as e:
            st.error(f"Chyba: {e}")
            folders = []

        if folders:
            folder_names = [f["name"] for f in folders]
            folder_map = {f["name"]: f["id"] for f in folders}
            chosen_folder = st.selectbox(
                "Otevřít složku",
                options=["--"] + folder_names,
                key=f"{nav_key}_sel",
            )
            if chosen_folder != "--":
                stack.append({"id": folder_map[chosen_folder], "name": chosen_folder})
                st.rerun()

        # List files in current folder
        try:
            folder_files = list_files(
                service, mime_types=mime_types, parent_id=current["id"]
            )
        except Exception as e:
            st.error(f"Chyba: {e}")
            folder_files = []

        if folder_files:
            _render_file_list(folder_files, key, "browse", multiple)
        else:
            st.caption("Žádné odpovídající soubory v této složce.")

    return []


def _render_file_list(files, key, source, multiple):
    """Render a list of Drive files with select buttons.

    For single-select: each file gets a button.
    For multi-select: checkboxes + confirm button.
    """
    session_key = f"drive_selected_{key}"

    if multiple:
        # Multi-select with checkboxes
        check_key = f"checks_{key}_{source}"
        selected_ids = []
        for f in files:
            label = f"{f['name']}"
            if f.get("modifiedTime"):
                label += f"  ({f['modifiedTime'][:10]})"
            checked = st.checkbox(
                label,
                key=f"{check_key}_{f['id']}",
            )
            if checked:
                selected_ids.append({"id": f["id"], "name": f["name"]})

        if selected_ids:
            if st.button(
                f"Potvrdit výběr ({len(selected_ids)})",
                key=f"confirm_{key}_{source}",
            ):
                st.session_state[session_key] = selected_ids
                st.rerun()
    else:
        # Single-select with buttons
        for f in files:
            label = f["name"]
            if f.get("modifiedTime"):
                label += f"  ({f['modifiedTime'][:10]})"
            if st.button(label, key=f"pick_{key}_{source}_{f['id']}"):
                st.session_state[session_key] = [
                    {"id": f["id"], "name": f["name"]}
                ]
                st.rerun()


def _drive_folder_pick_all(service, key, label, mime_types):
    """Navigate to a Drive folder and import ALL matching files from it.

    Shows a folder navigator; once the user is in the right folder,
    lists all matching files and offers a one-click "Import all" button.

    Args:
        service: Drive v3 service object.
        key: Unique key for session state.
        label: UI label.
        mime_types: List of MIME type strings to filter by.

    Returns:
        list of (file_id, file_name) tuples, or empty list.
    """
    from drive_utils import list_files, list_folders

    session_key = f"drive_folder_selected_{key}"
    if session_key not in st.session_state:
        st.session_state[session_key] = []  # list of {"id": ..., "name": ...}

    st.markdown(f"**{label}**")

    # --- Already selected -------------------------------------------------
    if st.session_state[session_key]:
        selected = st.session_state[session_key]
        st.caption(f"Vybráno {len(selected)} souborů ze složky")
        for f in selected:
            st.caption(f"  {f['name']}")
        if st.button("Zrušit výběr", key=f"clear_folder_{key}"):
            st.session_state[session_key] = []
            st.rerun()
        return [(f["id"], f["name"]) for f in selected]

    # --- Folder navigation ------------------------------------------------
    nav_key = f"fnav_{key}"
    if nav_key not in st.session_state:
        st.session_state[nav_key] = [{"id": "root", "name": "Disk"}]

    stack = st.session_state[nav_key]
    current = stack[-1]

    # Breadcrumb
    crumbs = " / ".join(item["name"] for item in stack)
    st.caption(f"📂 {crumbs}")

    # Navigation row
    col_up, col_folder = st.columns([1, 3])
    with col_up:
        if len(stack) > 1:
            if st.button("Nahoru", key=f"{nav_key}_up"):
                stack.pop()
                st.rerun()

    with col_folder:
        try:
            folders = list_folders(service, parent_id=current["id"])
        except Exception as e:
            st.error(f"Chyba: {e}")
            folders = []

        if folders:
            folder_names = [f["name"] for f in folders]
            folder_map = {f["name"]: f["id"] for f in folders}
            chosen_folder = st.selectbox(
                "Otevřít složku",
                options=["--"] + folder_names,
                key=f"{nav_key}_sel",
            )
            if chosen_folder != "--":
                stack.append({"id": folder_map[chosen_folder], "name": chosen_folder})
                st.rerun()

    # --- Show files in current folder -------------------------------------
    try:
        files_in_folder = list_files(
            service, mime_types=mime_types, parent_id=current["id"]
        )
    except Exception as e:
        st.error(f"Chyba: {e}")
        files_in_folder = []

    if files_in_folder:
        st.info(f"Nalezeno {len(files_in_folder)} souborů v této složce:")
        for f in files_in_folder:
            st.caption(f"  {f['name']}")

        if st.button(
            f"Importovat všech {len(files_in_folder)} souborů",
            key=f"import_all_{key}",
            type="primary",
        ):
            st.session_state[session_key] = [
                {"id": f["id"], "name": f["name"]}
                for f in files_in_folder
            ]
            st.rerun()
    else:
        st.caption("Žádné odpovídající soubory v této složce.")

    return []


# ---------------------------------------------------------------------------
# Sidebar — login
# ---------------------------------------------------------------------------

def render_sidebar():
    """Render the sidebar with optional Google login."""
    auth_available = _has_auth_config()

    with st.sidebar:
        st.header(APP_NAME)
        st.caption(f"verze {APP_VERSION}")
        st.markdown("---")

        if auth_available:
            if _is_logged_in():
                st.success(f"Přihlášen: {st.user.email}")
                if st.button("Odhlásit se"):
                    st.logout()
                    st.rerun()
            else:
                st.info("Pro přístup ke Google Drive se přihlaste.")
                if st.button("Přihlásit se přes Google"):
                    st.login()
        else:
            st.caption(
                "Google Drive není nakonfigurován. "
                "Přidejte OAuth credentials do .streamlit/secrets.toml."
            )

        st.markdown("---")
        st.markdown(
            "**Jak to funguje**\n"
            "1. Nahrajte (nebo vyberte z Drive) vstupní Excel soubory\n"
            "2. Nahrajte (nebo vyberte z Drive) šablony .docx\n"
            "3. Klepněte na **Generovat dokumenty**\n"
            "4. Stáhněte vygenerované dokumenty jako ZIP"
        )


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def main():
    render_sidebar()

    st.title("Generování dokumentace")

    logged_in = _is_logged_in()
    drive_service = None

    if logged_in:
        token = _get_access_token()
        if token:
            try:
                from drive_utils import get_drive_service
                drive_service = get_drive_service(token)
            except Exception as exc:
                st.warning(f"Nelze se připojit k Drive: {exc}")
                drive_service = None

    # ----- Inputs ----------------------------------------------------------

    st.subheader("Vstupní soubory")

    zakazka_path = None
    pravidla_path = None
    template_paths = []  # list of temp paths to .docx files
    templates_tmpdir = None  # will hold a tmpdir path if we copy files there

    # Source selector: Upload vs Google Drive
    source_options = ["Nahrát soubor"]
    if drive_service:
        source_options.append("Google Drive")

    # --- Zakazka -----------------------------------------------------------
    st.markdown("---")
    col_z1, col_z2 = st.columns([1, 1])

    with col_z1:
        z_source = st.radio(
            "Zakázka (.xlsx)",
            source_options,
            horizontal=True,
            key="z_source",
        )

    with col_z2:
        if z_source == "Nahrát soubor":
            z_file = st.file_uploader(
                "Soubor zakázky",
                type=["xlsx"],
                help="Excel soubor s proměnnými zakázky",
                key="z_upload",
                label_visibility="collapsed",
            )
            if z_file:
                zakazka_path = save_uploaded_file(z_file)
        else:
            from drive_utils import download_file, MIME_XLSX
            picker_results = _drive_search_and_pick(
                drive_service, "zakazka",
                "Zakázka (.xlsx)", [MIME_XLSX], multiple=False,
            )
            if picker_results:
                file_id, file_name = picker_results[0]
                cache_key = f"dl_zakazka_{file_id}"
                if cache_key not in st.session_state:
                    with st.spinner(f"Stahuji {file_name}..."):
                        data = download_file(drive_service, file_id)
                    st.session_state[cache_key] = save_bytes_to_temp(data, file_name)
                zakazka_path = st.session_state[cache_key]

    # --- Pravidla ----------------------------------------------------------
    st.markdown("---")
    col_p1, col_p2 = st.columns([1, 1])

    with col_p1:
        p_source = st.radio(
            "Pravidla (.xlsx)",
            source_options,
            horizontal=True,
            key="p_source",
        )

    with col_p2:
        if p_source == "Nahrát soubor":
            p_file = st.file_uploader(
                "Soubor pravidel",
                type=["xlsx"],
                help="Excel soubor s business pravidly",
                key="p_upload",
                label_visibility="collapsed",
            )
            if p_file:
                pravidla_path = save_uploaded_file(p_file)
        else:
            from drive_utils import download_file, MIME_XLSX
            picker_results = _drive_search_and_pick(
                drive_service, "pravidla",
                "Pravidla (.xlsx)", [MIME_XLSX], multiple=False,
            )
            if picker_results:
                file_id, file_name = picker_results[0]
                cache_key = f"dl_pravidla_{file_id}"
                if cache_key not in st.session_state:
                    with st.spinner(f"Stahuji {file_name}..."):
                        data = download_file(drive_service, file_id)
                    st.session_state[cache_key] = save_bytes_to_temp(data, file_name)
                pravidla_path = st.session_state[cache_key]

    # --- Templates ---------------------------------------------------------
    st.markdown("---")

    # For templates, Drive offers two modes: whole folder vs individual pick
    drive_tpl_options = ["Nahrát soubor"]
    if drive_service:
        drive_tpl_options.extend(["Drive — celá složka", "Drive — vybrat jednotlivě"])

    t_source = st.radio(
        "Šablony (.docx)",
        drive_tpl_options,
        horizontal=True,
        key="t_source",
    )

    if t_source == "Nahrát soubor":
        t_files = st.file_uploader(
            "Šablony Word",
            type=["docx"],
            accept_multiple_files=True,
            help="Všechny .docx šablony pro generování",
            key="t_upload",
        )
        if t_files:
            templates_tmpdir = tempfile.mkdtemp(prefix="tpl_")
            for uf in t_files:
                dest = os.path.join(templates_tmpdir, uf.name)
                with open(dest, "wb") as f:
                    f.write(uf.getvalue())
                template_paths.append(dest)

    elif t_source == "Drive — celá složka":
        from drive_utils import download_file, MIME_DOCX
        folder_results = _drive_folder_pick_all(
            drive_service, "tpl_folder",
            "Přejděte do složky se šablonami", [MIME_DOCX],
        )
        if folder_results:
            templates_tmpdir = tempfile.mkdtemp(prefix="tpl_")
            for file_id, file_name in folder_results:
                cache_key = f"dl_tpl_{file_id}"
                if cache_key not in st.session_state:
                    with st.spinner(f"Stahuji {file_name}..."):
                        data = download_file(drive_service, file_id)
                    st.session_state[cache_key] = data
                dest = os.path.join(templates_tmpdir, file_name)
                with open(dest, "wb") as fout:
                    fout.write(st.session_state[cache_key])
                template_paths.append(dest)

    elif t_source == "Drive — vybrat jednotlivě":
        from drive_utils import download_file, MIME_DOCX
        picker_results = _drive_search_and_pick(
            drive_service, "templates",
            "Šablony (.docx)", [MIME_DOCX], multiple=True,
        )
        if picker_results:
            templates_tmpdir = tempfile.mkdtemp(prefix="tpl_")
            for file_id, file_name in picker_results:
                cache_key = f"dl_tpl_{file_id}"
                if cache_key not in st.session_state:
                    with st.spinner(f"Stahuji {file_name}..."):
                        data = download_file(drive_service, file_id)
                    st.session_state[cache_key] = data
                dest = os.path.join(templates_tmpdir, file_name)
                with open(dest, "wb") as fout:
                    fout.write(st.session_state[cache_key])
                template_paths.append(dest)

    # ----- Status summary --------------------------------------------------
    st.markdown("---")
    st.subheader("Souhrn")

    col_s1, col_s2, col_s3 = st.columns(3)

    with col_s1:
        if zakazka_path:
            st.success(f"Zakázka: {os.path.basename(zakazka_path)}")
        else:
            st.warning("Zakázka: chybí")

    with col_s2:
        if pravidla_path:
            st.success(f"Pravidla: {os.path.basename(pravidla_path)}")
        else:
            st.warning("Pravidla: chybí")

    with col_s3:
        if template_paths:
            st.success(f"Šablony: {len(template_paths)} souborů")
        else:
            st.warning("Šablony: chybí")

    all_ready = zakazka_path and pravidla_path and template_paths

    # ----- Generate --------------------------------------------------------
    st.markdown("---")

    if st.button(
        "Generovat dokumenty",
        type="primary",
        disabled=not all_ready,
    ):
        with st.spinner("Generuji dokumenty..."):
            progress_placeholder = st.empty()
            log_placeholder = st.empty()

            def log_callback(msg):
                log_placeholder.text(msg)

            # Temp dirs for output, converted templates, logs
            output_tmpdir = tempfile.mkdtemp(prefix="out_")
            converted_tmpdir = tempfile.mkdtemp(prefix="conv_")
            logs_tmpdir = tempfile.mkdtemp(prefix="logs_")

            try:
                progress_placeholder.info("Spouštím generování...")

                result = run_pipeline(
                    zakazka_path=zakazka_path,
                    pravidla_path=pravidla_path,
                    templates_dir=templates_tmpdir,
                    output_dir=output_tmpdir,
                    templates_converted_dir=converted_tmpdir,
                    logs_dir=logs_tmpdir,
                    log_callback=log_callback,
                )

                progress_placeholder.empty()

                if result["success"]:
                    st.success(
                        f"Hotovo! Vygenerováno "
                        f"{result['generated_count']}/{result['total_count']} "
                        f"dokumentů"
                    )
                else:
                    st.error("Generování selhalo")
                    if result.get("errors"):
                        for err in result["errors"]:
                            st.error(f"  {err}")

                    if result["generated_count"] > 0:
                        st.warning(
                            f"Částečně úspěšné: "
                            f"{result['generated_count']}/{result['total_count']} "
                            f"dokumentů"
                        )

                # Offer ZIP download if any docs were generated
                output_folder = result.get("output_folder", "")
                if output_folder and os.path.exists(output_folder):
                    with st.spinner("Vytvářím ZIP archiv..."):
                        zip_buffer = zip_directory(output_folder)

                    st.download_button(
                        label="Stáhnout dokumenty jako ZIP",
                        data=zip_buffer,
                        file_name=f"dokumenty_{os.path.basename(output_folder)}.zip",
                        mime="application/zip",
                    )

                with st.expander("Zobrazit report"):
                    st.text(result.get("report_text", ""))

            except Exception as exc:
                progress_placeholder.empty()
                st.error(f"Došlo k chybě: {exc}")
                logger.exception("Pipeline error in web app")

            finally:
                # Always cleanup temp dirs (keep zakazka and pravidla for debugging)
                cleanup_temp_dirs(templates_tmpdir, converted_tmpdir, output_tmpdir)


if __name__ == "__main__":
    main()

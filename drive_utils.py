"""
Google Drive API utilities for the Elevator Documentation web app.

Provides helpers to list folders/files, navigate the Drive tree, and download
files using an OAuth2 access token obtained from st.login().
"""

import io
import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# MIME types used for filtering
MIME_FOLDER = "application/vnd.google-apps.folder"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_DOCX = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

# Fields returned for every file listing
_FILE_FIELDS = "nextPageToken, files(id, name, mimeType, modifiedTime, size)"


def get_drive_service(access_token):
    """Build a Google Drive v3 service from a raw access token.

    Args:
        access_token: OAuth2 access token string (from st.user.tokens["access"]).

    Returns:
        googleapiclient Resource for Drive v3.

    Raises:
        HttpError: If the token is invalid or expired (HTTP 401).
    """
    creds = Credentials(token=access_token)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_folders(service, parent_id=None, page_size=100):
    """List folders inside a parent folder (or root if parent_id is None).

    Args:
        service: Drive v3 service resource.
        parent_id: Google Drive folder ID. None means "root".
        page_size: Maximum number of results.

    Returns:
        List of dicts with keys: id, name, mimeType, modifiedTime.
    """
    parent = parent_id or "root"
    query = (
        f"'{parent}' in parents "
        f"and mimeType = '{MIME_FOLDER}' "
        f"and trashed = false"
    )
    try:
        resp = service.files().list(
            q=query,
            pageSize=page_size,
            fields=_FILE_FIELDS,
            orderBy="name",
        ).execute()
        return resp.get("files", [])
    except HttpError as e:
        logger.error("Drive list_folders failed: %s", e)
        raise


def list_files(service, mime_types=None, parent_id=None, page_size=100):
    """List files (non-folder) in a parent folder, optionally filtered by MIME type.

    Args:
        service: Drive v3 service resource.
        mime_types: Optional list of MIME type strings to filter by.
                    Example: [MIME_XLSX] or [MIME_DOCX].
        parent_id: Google Drive folder ID. None means "root".
        page_size: Maximum number of results.

    Returns:
        List of dicts with keys: id, name, mimeType, modifiedTime, size.
    """
    parent = parent_id or "root"
    query = (
        f"'{parent}' in parents "
        f"and mimeType != '{MIME_FOLDER}' "
        f"and trashed = false"
    )
    if mime_types:
        mime_clauses = " or ".join(
            f"mimeType = '{m}'" for m in mime_types
        )
        query = (
            f"'{parent}' in parents "
            f"and ({mime_clauses}) "
            f"and trashed = false"
        )

    try:
        resp = service.files().list(
            q=query,
            pageSize=page_size,
            fields=_FILE_FIELDS,
            orderBy="name",
        ).execute()
        return resp.get("files", [])
    except HttpError as e:
        logger.error("Drive list_files failed: %s", e)
        raise


def download_file(service, file_id):
    """Download a file from Drive and return its bytes.

    Works for regular (binary) files like .xlsx and .docx.
    Does NOT work for Google Workspace native files (Docs, Sheets) —
    those require export_file() instead.

    Args:
        service: Drive v3 service resource.
        file_id: Google Drive file ID.

    Returns:
        bytes — the file content.
    """
    try:
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
        return buffer.getvalue()
    except HttpError as e:
        logger.error("Drive download_file failed for %s: %s", file_id, e)
        raise


def is_token_expired_error(error):
    """Check whether an HttpError indicates an expired/invalid token (401).

    Args:
        error: A googleapiclient.errors.HttpError instance.

    Returns:
        True if the status is 401 (Unauthorized).
    """
    return isinstance(error, HttpError) and error.resp.status == 401


def search_files(service, query_text, mime_types=None, page_size=20):
    """Search for files across the entire Drive by name.

    Uses the Drive API ``fullText contains`` query which searches file names
    and content.  Results are ordered by relevance (Drive default).

    Args:
        service: Drive v3 service resource.
        query_text: Free-text search string (e.g. "zakazka").
        mime_types: Optional list of MIME types to filter by.
        page_size: Maximum number of results (default 20).

    Returns:
        List of dicts with keys: id, name, mimeType, modifiedTime, size.
    """
    clauses = [
        f"name contains '{query_text}'",
        "trashed = false",
        f"mimeType != '{MIME_FOLDER}'",
    ]
    if mime_types:
        mime_clauses = " or ".join(f"mimeType = '{m}'" for m in mime_types)
        clauses.append(f"({mime_clauses})")

    query = " and ".join(clauses)

    try:
        resp = service.files().list(
            q=query,
            pageSize=page_size,
            fields=_FILE_FIELDS,
            orderBy="modifiedTime desc",
        ).execute()
        return resp.get("files", [])
    except HttpError as e:
        logger.error("Drive search_files failed: %s", e)
        raise


def list_recent_files(service, mime_types=None, page_size=10):
    """List most recently modified files, optionally filtered by MIME type.

    Useful for a "recent files" quick-access section.

    Args:
        service: Drive v3 service resource.
        mime_types: Optional list of MIME types to filter by.
        page_size: Maximum number of results (default 10).

    Returns:
        List of dicts with keys: id, name, mimeType, modifiedTime, size.
    """
    clauses = [
        "trashed = false",
        f"mimeType != '{MIME_FOLDER}'",
    ]
    if mime_types:
        mime_clauses = " or ".join(f"mimeType = '{m}'" for m in mime_types)
        clauses.append(f"({mime_clauses})")

    query = " and ".join(clauses)

    try:
        resp = service.files().list(
            q=query,
            pageSize=page_size,
            fields=_FILE_FIELDS,
            orderBy="modifiedTime desc",
        ).execute()
        return resp.get("files", [])
    except HttpError as e:
        logger.error("Drive list_recent_files failed: %s", e)
        raise

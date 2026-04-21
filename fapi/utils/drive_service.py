# fapi/utils/drive_service.py
import os
import io
from typing import Optional
import requests
import shutil

from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


_SCOPES_ENV = os.getenv("GOOGLE_DRIVE_SCOPES", "").strip()
SCOPES = [s.strip() for s in _SCOPES_ENV.split(",") if s.strip()] if _SCOPES_ENV else []

# Adjust this if your project root is different
BASE_DIR = Path(__file__).resolve().parents[2]
TOKEN_PATH = BASE_DIR / "token.json"

from dotenv import load_dotenv
load_dotenv()

TEMP_FOLDER_ID = os.getenv("GOOGLE_DRIVE_TEMP_FOLDER_ID")
ROOT_USER_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID")
LOCAL_UPLOAD_DIR = BASE_DIR / "local_approval_uploads"
LOCAL_ID_PREFIX = "local://"
ENABLE_LOCAL_UPLOAD_FALLBACK = os.getenv("ENABLE_LOCAL_UPLOAD_FALLBACK", "false").lower() == "true"


def _ensure_local_upload_dir() -> None:
    LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _is_local_file_id(file_id: str) -> bool:
    return isinstance(file_id, str) and file_id.startswith(LOCAL_ID_PREFIX)


def _local_relpath_from_id(file_id: str) -> str:
    return file_id.replace(LOCAL_ID_PREFIX, "", 1)


def _local_path_from_id(file_id: str) -> Path:
    rel = _local_relpath_from_id(file_id)
    return LOCAL_UPLOAD_DIR / rel


def _build_local_file_id(path: Path) -> str:
    rel = path.relative_to(LOCAL_UPLOAD_DIR).as_posix()
    return f"{LOCAL_ID_PREFIX}{rel}"

def _creds() -> Credentials:
    if not TOKEN_PATH.exists():
        raise RuntimeError(f"token.json not found at {TOKEN_PATH}. Run auth flow again.")

    # Do not force-refresh with a scope set that may not match token.json grant.
    # If GOOGLE_DRIVE_SCOPES is provided explicitly, respect it; otherwise use token scopes.
    if SCOPES:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    else:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))

    if creds.expired or not creds.valid:
        try:
            if creds.refresh_token:
                creds.refresh(Request())

                # 🔥 SAVE refreshed token back to file
                TOKEN_PATH.write_text(creds.to_json())

            else:
                raise RuntimeError("No refresh token available. Re-auth required.")

        except Exception as e:
            raise RuntimeError(
                f"Google auth refresh failed. You must re-login. Reason: {str(e)}"
            )

    return creds


def _service():
    creds = _creds()
    return build("drive", "v3", credentials=creds)


def upload_to_temp(file_bytes: bytes, mime_type: str, uid_filename: str) -> str:
    print("TEMP_FOLDER_ID:", TEMP_FOLDER_ID)
    try:
        if not TEMP_FOLDER_ID:
            raise RuntimeError("GOOGLE_DRIVE_TEMP_FOLDER_ID is not configured")

        creds = _creds()

        boundary = "foo_bar_baz"
        metadata_part = (
            f'{{"name": "{uid_filename}", "parents": ["{TEMP_FOLDER_ID}"]}}'
        )

        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{metadata_part}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--".encode("utf-8")

        headers = {
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": f'multipart/related; boundary="{boundary}"',
        }

        upload_url = "https://www.googleapis.com/upload/drive/v3/files"
        params = {"uploadType": "multipart"}

        resp = requests.post(upload_url, headers=headers, params=params, data=body)
        if not resp.ok:
            print("Drive error:", resp.status_code, resp.text)
        resp.raise_for_status()
        return resp.json()["id"]
    except Exception as drive_err:
        if not ENABLE_LOCAL_UPLOAD_FALLBACK:
            raise
        print(f"DRIVE_UNAVAILABLE_FALLBACK_LOCAL: {drive_err}")
        _ensure_local_upload_dir()
        safe_name = uid_filename.replace("\\", "_").replace("/", "_")
        local_path = LOCAL_UPLOAD_DIR / safe_name
        local_path.write_bytes(file_bytes)
        return _build_local_file_id(local_path)

# fapi/utils/drive_service.py

def rename_file(file_id: str, username: str, original_name: str, document_type: str) -> None:
    if _is_local_file_id(file_id):
        local_path = _local_path_from_id(file_id)
        if not local_path.exists():
            return
        _, ext = os.path.splitext(original_name)
        ext = ext or ""
        new_name = f"{username}_{document_type}{ext}"
        new_path = local_path.with_name(new_name)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.rename(new_path)
        return

    svc = _service()

    _, ext = os.path.splitext(original_name)
    ext = ext or ""

    new_name = f"{username}_{document_type}{ext}"
    # e.g. khaja_identity.pdf

    svc.files().update(
        fileId=file_id,
        body={"name": new_name},
        fields="id, name",
    ).execute()


def build_final_filename(uid: str, username: str, email: str, original_filename: str) -> str:
    # Prefer username; if not available, fall back to email
    base = username or email

    # Get extension from original filename, default to empty if none
    ext = ""
    if "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[1]

    # e.g. "khaja.pdf" or "khajainnovopath@gmail.com.pdf"
    return f"{base}{ext}"

def _find_user_folder(username: str) -> Optional[str]:
    svc = _service()
    query = (
        "mimeType='application/vnd.google-apps.folder' "
        f"and name='{username}' and trashed=false and '{ROOT_USER_FOLDER_ID}' in parents"
    )
    res = svc.files().list(q=query, fields="files(id,name)", pageSize=1).execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None


def get_or_create_user_folder(username: str) -> str:
    svc = _service()

    username = username.strip().lower()
    print("FOLDER USERNAME:", username)

    existing = _find_user_folder(username)
    if existing:
        return existing

    meta = {
        "name": username,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [ROOT_USER_FOLDER_ID],
    }

    folder = svc.files().create(body=meta, fields="id").execute()
    folder_id = folder.get("id")

    if not folder_id:
        raise ValueError(f"Failed to create folder for user {username}")

    return folder_id

def move_file_to_user_folder(file_id: str, username: str) -> None:
    if _is_local_file_id(file_id):
        source = _local_path_from_id(file_id)
        if not source.exists():
            return
        target_dir = LOCAL_UPLOAD_DIR / username.strip().lower()
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        shutil.move(str(source), str(target))
        return

    print("MOVE_FILE:", file_id, "→", username)
    svc = _service()
    user_folder_id = get_or_create_user_folder(username)
    print("USER_FOLDER_ID:", user_folder_id)

    f = svc.files().get(fileId=file_id, fields="parents").execute()
    print("BEFORE_PARENTS:", f.get("parents", []))
    prev_parents = ",".join(f.get("parents", []))

    result = svc.files().update(
        fileId=file_id,
        addParents=user_folder_id,
        removeParents=prev_parents,
        fields="id,parents",
    ).execute()
    print("AFTER_PARENTS:", result.get("parents", []))

def delete_file(file_id: str) -> None:
    if _is_local_file_id(file_id):
        local_path = _local_path_from_id(file_id)
        if local_path.exists():
            local_path.unlink()
        return

    svc = _service()
    try:
        svc.files().delete(fileId=file_id).execute()
        print(f"Deleted file {file_id}")
    except Exception as e:
        print("Delete failed:", str(e))

def get_file_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"

def download_file_bytes(file_id: str) -> bytes:
    if _is_local_file_id(file_id):
        local_path = _local_path_from_id(file_id)
        if not local_path.exists():
            raise FileNotFoundError(f"Local approval file not found: {local_path}")
        return local_path.read_bytes()

    svc = _service()
    request = svc.files().get_media(fileId=file_id)
    file_io = io.BytesIO()
    from googleapiclient.http import MediaIoBaseDownload
    downloader = MediaIoBaseDownload(file_io, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return file_io.getvalue()


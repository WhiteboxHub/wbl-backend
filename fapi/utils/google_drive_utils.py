import os
import io
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Path to your service account JSON file (Fallback)
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')

# OAuth2 Configuration (Production Ready)
CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
REFRESH_TOKEN = os.getenv('GOOGLE_REFRESH_TOKEN')

# The parent folder ID in Google Drive
PARENT_FOLDER_ID = os.getenv('GOOGLE_DRIVE_PARENT_FOLDER_ID')

def get_drive_service():
    """
    Returns a Google Drive service object.
    Prioritizes OAuth2 (User Quota) over Service Account.
    """
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')

    # 1. Try OAuth2 (Production Recommended)
    if client_id and client_secret and refresh_token:
        try:
            creds = Credentials(
                None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            
            # Refresh if needed
            if not creds.valid:
                creds.refresh(Request())
                
            return build('drive', 'v3', credentials=creds)
        except Exception as oauth_err:
            logger.error(f"OAuth2 Authentication failed: {oauth_err}")
            # Fall through to service account
            
    # 2. Try Service Account (Fallback to file)
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        try:
            scopes = ['https://www.googleapis.com/auth/drive']
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=scopes)
            return build('drive', 'v3', credentials=creds)
        except Exception as sa_err:
            logger.error(f"Service Account Authentication failed: {sa_err}")
            
    # 3. Try Service Account (Fallback to environment variable JSON)
    google_creds_json = os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON') or os.getenv('GOOGLE_CREDENTIALS_JSON')
    if google_creds_json:
        import json
        try:
            scopes = ['https://www.googleapis.com/auth/drive']
            clean = google_creds_json.strip()
            if clean.startswith("'") and clean.endswith("'"):
                clean = clean[1:-1]
            info = json.loads(clean)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=scopes)
            return build('drive', 'v3', credentials=creds)
        except Exception as sa_env_err:
            logger.error(f"Service Account (Env) Authentication failed: {sa_env_err}")
            
    logger.error("No valid Google Drive credentials found (OAuth2 or Service Account)")
    return None

def create_drive_folder(folder_name: str, parent_id: str = None):
    """Finds or creates a folder in Google Drive and shares it with recruiters."""
    service = get_drive_service()
    if not service:
        return None

    # Use provided parent_id or fall back to PARENT_FOLDER_ID from env
    actual_parent_id = parent_id or os.getenv('GOOGLE_DRIVE_PARENT_FOLDER_ID')

    # Check if folder already exists
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if actual_parent_id:
        query += f" and '{actual_parent_id}' in parents"
    
    try:
        results = service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, webViewLink)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = results.get('files', [])
        
        folder = None
        if files:
            folder = files[0]
        else:
            # Create new folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [actual_parent_id] if actual_parent_id else []
            }
            folder = service.files().create(
                body=file_metadata, 
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()

        # SHARE THE FOLDER with recruiters/admins from .env
        if folder:
            # Get recipients from .env
            recruiting_raw = os.getenv('TO_RECRUITING_EMAIL', '')
            admin_raw = os.getenv('TO_ADMIN_EMAIL', '')
            
            # Combine and clean
            all_raw = f"{recruiting_raw},{admin_raw}"
            recruiter_emails = list(set([e.strip() for e in all_raw.split(',') if e.strip()]))
            
            for email in recruiter_emails:
                if email:
                    try:
                        permission = {
                            'type': 'user',
                            'role': 'writer',
                            'emailAddress': email
                        }
                        service.permissions().create(
                            fileId=folder['id'],
                            body=permission,
                            fields='id',
                            supportsAllDrives=True
                        ).execute()
                        logger.info(f"Shared folder {folder_name} with {email}")
                    except Exception as share_err:
                        logger.error(f"Failed to share folder with {email}: {share_err}")

        return folder
    except Exception as e:
        logger.error(f"Error in create_drive_folder: {e}")
        return None

def get_or_create_root_folder(folder_name: str = "WBL Candidates"):
    """Ensures a default root folder exists for all candidates."""
    # We search globally for this folder first
    service = get_drive_service()
    if not service:
        return None
    
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    try:
        results = service.files().list(q=query, fields='files(id)').execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        
        # Create it if it doesn't exist
        folder = create_drive_folder(folder_name)
        return folder['id'] if folder else None
    except Exception as e:
        logger.error(f"Error getting/creating root folder: {e}")
        return None

def ensure_candidate_folder(candidate_id: int, candidate_name: str, existing_folder_id: str = None):
   
    root_id = get_or_create_root_folder()
    if not root_id:
        logger.error("Could not find or create root 'WBL Candidates' folder")
        return None
    
    expected_name = f"{candidate_id} - {candidate_name}"
    
    # If we already have a folder ID, verify/update the name
    if existing_folder_id:
        service = get_drive_service()
        if service:
            try:
                # Get current metadata
                file = service.files().get(fileId=existing_folder_id, fields='id, name, trashed').__getattribute__("execute")()
                if not file.get('trashed') and file.get('name') != expected_name:
                    rename_drive_folder(existing_folder_id, expected_name)
                    logger.info(f"Renamed folder {existing_folder_id} to {expected_name}")
                return {'id': existing_folder_id, 'webViewLink': f"https://drive.google.com/drive/folders/{existing_folder_id}"}
            except Exception as e:
                logger.error(f"Error checking/renaming existing folder {existing_folder_id}: {e}")
                # Fall through to name-based search or creation
    
    folder = create_drive_folder(expected_name, parent_id=root_id)
    return folder

def rename_drive_folder(folder_id: str, new_name: str):
    """Renames an existing Google Drive folder."""
    service = get_drive_service()
    if not service:
        return None
    
    try:
        file = service.files().update(
            fileId=folder_id,
            body={'name': new_name},
            fields='id, name',
            supportsAllDrives=True
        ).execute()
        return file
    except Exception as e:
        logger.error(f"Error renaming folder {folder_id}: {e}")
        return None


def upload_to_drive(file_content: bytes, filename: str, folder_id: str, mimetype: str = 'application/octet-stream'):
    service = get_drive_service()
    if not service:
        return None

    try:
        if not mimetype:
            mimetype = 'application/octet-stream'
            
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        
        fh = io.BytesIO(file_content)
        # Disable resumable for small files to increase reliability
        media = MediaIoBaseUpload(fh, mimetype=mimetype, resumable=False)
        
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()
        return file.get('id')
    except Exception as e:
        logger.error(f"Error in upload_to_drive: {e}")
        return None

def get_candidate_files(folder_id: str):
    """Lists all files in a specific Google Drive folder."""
    service = get_drive_service()
    if not service:
        return []

    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name, webViewLink)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        return results.get('files', [])
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return []

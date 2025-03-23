from fastapi import APIRouter, File, UploadFile, HTTPException
from azure.storage.blob import BlobServiceClient
import os
import datetime
import uuid
from ..config import BLOB_URL, BLOB_TOKEN, CONTAINER_NAME

# Load environment variables
# load_dotenv()

# # Azure Blob Storage Configuration
# BLOB_URL = os.getenv("AZURE_BLOB_URL")
# BLOB_TOKEN = os.getenv("AZURE_BLOB_TOKEN")
# CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")

# Initialize Azure Blob Storage client
blob_service_client = BlobServiceClient(account_url=BLOB_URL, credential=BLOB_TOKEN)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)

# Allowed file extensions
ALLOWED_EXTENSIONS = {"pdf", "docx", "xlsx"}

# Initialize Router
router = APIRouter(prefix="/documents", tags=["Document Upload"])

# 🔹 1️⃣ **UPLOAD DOCUMENT API**
@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Uploads a document (PDF, Word, Excel) to Azure Blob Storage.
    Returns the storage URL.
    """
    # ✅ Validate file format
    file_extension = file.filename.split(".")[-1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and XLSX files are allowed")

    # ✅ Generate a unique filename
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]  # Short unique identifier
    new_filename = f"document_{timestamp}_{unique_id}.{file_extension}"

    # ✅ Upload file to Azure Blob
    blob_client = container_client.get_blob_client(new_filename)
    blob_client.upload_blob(file.file, overwrite=True)

    # ✅ Construct file URL
    file_url = f"{BLOB_URL}/{CONTAINER_NAME}/{new_filename}?{BLOB_TOKEN.lstrip('?')}"

    return {"message": "File uploaded successfully", "file_url": file_url}

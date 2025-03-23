from fastapi import APIRouter, File, UploadFile, HTTPException
from azure.storage.blob import BlobServiceClient
import os
import datetime
import uuid
import fitz  # PyMuPDF for PDF text extraction
import openai
import tiktoken
from azure.cosmos import CosmosClient
import tempfile

from ..config import (
    BLOB_URL, BLOB_TOKEN, CONTAINER_NAME, 
    COSMOS_DB_URL, COSMOS_DB_KEY, DATABASE_NAME, CONTAINER_NAME_cosmos, 
    OPENAI_API_KEY
)

# ✅ Initialize Azure Clients
blob_service_client = BlobServiceClient(account_url=BLOB_URL, credential=BLOB_TOKEN)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)
cosmos_client = CosmosClient(COSMOS_DB_URL, COSMOS_DB_KEY)
cosmos_db = cosmos_client.get_database_client(DATABASE_NAME)
cosmos_container = cosmos_db.get_container_client(CONTAINER_NAME_cosmos)

openai.api_key = OPENAI_API_KEY

# ✅ Allowed file extensions
ALLOWED_EXTENSIONS = {"pdf"}

# ✅ Initialize Router
router = APIRouter(prefix="/documents", tags=["Document"])

# 🔹 **Upload & Process API**
@router.post("/upload")
async def upload_and_process_document(file: UploadFile = File(...)):
    """
    Uploads a document (PDF) to Azure Blob Storage, extracts text,
    generates embeddings, and stores them in CosmosDB.
    """
    # ✅ Validate file type
    file_extension = file.filename.split(".")[-1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # ✅ Generate a unique filename
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    new_filename = f"document_{timestamp}_{unique_id}.{file_extension}"

    # ✅ Upload file to Azure Blob
    blob_client = container_client.get_blob_client(new_filename)
    blob_client.upload_blob(file.file, overwrite=True)

    # ✅ Save file temporarily before processing
    temp_path = f"/tmp/{new_filename}"  # Use Linux tmp directory
    try:
        with open(temp_path, "wb") as temp_file:
            temp_file.write(await file.read())  # ✅ Properly save the file

        # ✅ Process PDF and store embeddings
        process_pdf_and_store(temp_path, new_filename)

    except Exception as e:
        print(f"❌ Error processing file: {e}")
        raise HTTPException(status_code=500, detail="Error processing document.")

    finally:
        # ✅ Cleanup: Remove temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return {"message": "File uploaded & processed successfully", "file_url": new_filename}

# 🔹 **Extract Text from PDF**
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text("text") + "\n"
    except Exception as e:
        print(f"❌ Error extracting text: {e}")
    return text.strip()

# 🔹 **Split Text into Chunks (500 tokens)**
def split_text(text, chunk_size=500):
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)

    chunks = []
    for i in range(0, len(tokens), chunk_size):
        chunk = tokens[i : i + chunk_size]
        chunks.append(encoding.decode(chunk))

    return chunks

# 🔹 **Generate Vector Embeddings**
def generate_embeddings(text_chunks):
    embeddings = []
    for i, chunk in enumerate(text_chunks):
        try:
            response = openai.embeddings.create(
                model="text-embedding-ada-002",  
                input=[chunk]  
            )
            embeddings.append(response.data[0].embedding)
        except Exception as e:
            print(f"❌ Error generating embeddings for chunk {i}: {e}")
    return embeddings

# 🔹 **Store Vectors in CosmosDB**
def store_vectors_in_cosmos(file_name, text_chunks, vectors):
    if not vectors:
        print("❌ No vectors to store.")
        return

    for i in range(len(text_chunks)):
        doc_id = str(uuid.uuid4())

        item = {
            "id": doc_id,
            "file_name": file_name,
            "chunk_index": i,
            "text": text_chunks[i],
            "vector": vectors[i],
        }

        try:
            cosmos_container.upsert_item(item)
            print(f"✅ Stored chunk {i+1}/{len(text_chunks)} in CosmosDB")
        except Exception as e:
            print(f"❌ Error storing chunk {i+1}: {e}")

# 🔹 **Main Processing Function**
def process_pdf_and_store(pdf_path, file_name):
    text = extract_text_from_pdf(pdf_path)

    if not text:
        print("❌ No text extracted from the document.")
        return

    text_chunks = split_text(text)
    vectors = generate_embeddings(text_chunks)
    store_vectors_in_cosmos(file_name, text_chunks, vectors)

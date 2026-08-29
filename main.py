import os
import csv
import io
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException

# Initialize the FastAPI app
app = FastAPI(title="Agency AI Operations Engine")

# Create a folder to save the uploaded files locally
# This prevents us from losing data if the database isn't set up yet
os.makedirs("uploads", exist_ok=True)

@app.get("/health")
async def health_check():
    return {"status": "Engine is running"}

@app.post("/upload-csv/")
async def upload_csv(file: UploadFile = File(...)):
    # 1. Validate the file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    # 2. Read the file contents into memory
    contents = await file.read()
    
    # 3. Save the file locally in the "uploads" folder with a unique name
    unique_id = str(uuid.uuid4())
    _, ext = os.path.splitext(file.filename)
    file_location = f"uploads/{unique_id}{ext}"
    with open(file_location, "wb") as f:
        f.write(contents)

    # 4. Parse the CSV to extract the headers (First row)
    # We have to decode the raw bytes into text (utf-8) for the CSV reader to work
    decoded_contents = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.reader(decoded_contents)
    
    # Extract the first row (headers)
    headers = next(csv_reader)

    # 5. Return a success response
    return {
        "filename": file.filename,
        "saved_to": file_location,
        "headers_detected": headers,
        "status": "File ingested successfully. Ready for database."
    }
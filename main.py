import os
import csv
import io
import uuid
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Client, Report

Base.metadata.create_all(bind=engine)

DEFAULT_CLIENT_NAME = "Default Client"

# Initialize the FastAPI app
app = FastAPI(title="Agency AI Operations Engine")

# Create a folder to save the uploaded files locally
os.makedirs("uploads", exist_ok=True)


@app.get("/health")
async def health_check():
    return {"status": "Engine is running"}


def get_or_create_default_client(db: Session) -> Client:
    client = db.query(Client).filter(Client.name == DEFAULT_CLIENT_NAME).first()
    if client is None:
        client = Client(name=DEFAULT_CLIENT_NAME)
        db.add(client)
        db.flush()
    return client


@app.post("/upload-csv/")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Validate the file type
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    # 2. Read the file contents into memory
    contents = await file.read()

    # 3. Parse headers before writing anything, so empty/invalid files fail early
    try:
        decoded_contents = io.StringIO(contents.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV file must be valid UTF-8 text.")

    csv_reader = csv.reader(decoded_contents)
    try:
        headers = next(csv_reader)
    except StopIteration:
        raise HTTPException(status_code=400, detail="CSV file is empty.")

    # 4. Save the file locally with a unique name
    unique_id = str(uuid.uuid4())
    _, ext = os.path.splitext(file.filename)
    unique_filename = f"{unique_id}{ext}"
    file_location = f"uploads/{unique_filename}"
    with open(file_location, "wb") as f:
        f.write(contents)

    # 5. Persist a Client (reused) and a Report row for this upload
    client = get_or_create_default_client(db)
    report = Report(
        client_id=client.id,
        original_filename=file.filename,
        unique_filename=unique_filename,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "filename": file.filename,
        "saved_to": file_location,
        "headers_detected": headers,
        "client_id": client.id,
        "report_id": report.id,
        "status": "File ingested and report saved.",
    }
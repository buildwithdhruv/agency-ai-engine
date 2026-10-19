import os
import csv
import io
import uuid
from datetime import date

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Client, Metric, Report

Base.metadata.create_all(bind=engine)

DEFAULT_CLIENT_NAME = "Default Client"
REQUIRED_HEADERS = [
    "date",
    "campaign_name",
    "impressions",
    "clicks",
    "spend",
    "conversions",
]

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


def _parse_int(value: str, field: str, row_num: int) -> int:
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Row {row_num}: '{field}' must be a whole number, got '{value}'.")


def _parse_float(value: str, field: str, row_num: int) -> float:
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Row {row_num}: '{field}' must be a number, got '{value}'.")


def parse_csv_metrics(contents: bytes) -> tuple[list[str], list[dict]]:
    try:
        decoded = io.StringIO(contents.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ValueError("CSV file must be valid UTF-8 text.") from exc

    reader = csv.DictReader(decoded)
    if reader.fieldnames is None:
        raise ValueError("CSV file is empty.")

    headers = [header.strip() for header in reader.fieldnames]
    reader.fieldnames = headers
    missing = [name for name in REQUIRED_HEADERS if name not in headers]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}.")

    metrics = []
    for row_num, raw_row in enumerate(reader, start=2):
        row = {key: (value or "").strip() for key, value in raw_row.items()}
        if not any(row.get(name) for name in REQUIRED_HEADERS):
            continue

        campaign_name = row.get("campaign_name", "")
        if not campaign_name:
            raise ValueError(f"Row {row_num}: 'campaign_name' is required.")

        try:
            metric_date = date.fromisoformat(row.get("date", ""))
        except ValueError as exc:
            raise ValueError(
                f"Row {row_num}: 'date' must be YYYY-MM-DD, got '{row.get('date', '')}'."
            ) from exc

        metrics.append(
            {
                "date": metric_date,
                "campaign_name": campaign_name,
                "impressions": _parse_int(row.get("impressions", ""), "impressions", row_num),
                "clicks": _parse_int(row.get("clicks", ""), "clicks", row_num),
                "spend": _parse_float(row.get("spend", ""), "spend", row_num),
                "conversions": _parse_int(row.get("conversions", ""), "conversions", row_num),
            }
        )

    if not metrics:
        raise ValueError("CSV has a header row but no data rows.")

    return headers, metrics


@app.post("/upload-csv/")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Validate the file type
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    # 2. Read and parse before writing anything, so invalid files fail early
    contents = await file.read()
    try:
        headers, metric_rows = parse_csv_metrics(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 3. Save the file locally with a unique name
    unique_id = str(uuid.uuid4())
    _, ext = os.path.splitext(file.filename)
    unique_filename = f"{unique_id}{ext}"
    file_location = f"uploads/{unique_filename}"
    with open(file_location, "wb") as f:
        f.write(contents)

    # 4. Persist Client, Report, and Metric rows in one transaction
    client = get_or_create_default_client(db)
    report = Report(
        client_id=client.id,
        original_filename=file.filename,
        unique_filename=unique_filename,
    )
    db.add(report)
    db.flush()

    for metric_row in metric_rows:
        db.add(Metric(report_id=report.id, **metric_row))

    db.commit()
    db.refresh(report)

    return {
        "filename": file.filename,
        "saved_to": file_location,
        "headers_detected": headers,
        "client_id": client.id,
        "report_id": report.id,
        "metric_count": len(metric_rows),
        "status": "File ingested and metrics saved.",
    }

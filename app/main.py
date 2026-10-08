import shutil
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Feature, UploadedFile
from app.processor import process_file

app = FastAPI(title="Geospatial File Measurement API")

# Create the tables in geo.db if they don't exist yet
Base.metadata.create_all(engine)

ALLOWED_EXTENSIONS = {".kml", ".zip"}
SHAPEFILE_PARTS = {".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix"}
SHAPEFILE_MESSAGE = (
    "Do not upload individual shapefile parts. Instead, zip all the shapefile parts "
    "into a single .zip file and upload that."
)
STORAGE_DIR = Path("storage")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/files/", status_code=201)
def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    extension = Path(file.filename).suffix.lower()

    # Reject shapefile parts uploaded on their own, with a specific hint
    if extension in SHAPEFILE_PARTS:
        raise HTTPException(status_code=400, detail=SHAPEFILE_MESSAGE)

    # Reject any other unsupported type
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. Upload a .kml file, or a .zip containing a shapefile.",
        )

    # Save the upload under its own folder
    file_id = uuid.uuid4().hex
    (STORAGE_DIR / file_id).mkdir(parents=True, exist_ok=True)
    destination_path = STORAGE_DIR / file_id / f"uploaded{extension}"
    with open(destination_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    record = UploadedFile(id=file_id, filename=file.filename)

    # Read and measure the file; a bad file is recorded as FAILED rather than crashing
    try:
        result = process_file(destination_path)
        record.status = "COMPLETED"
        record.crs = result["crs"]
        record.feature_count = result["feature_count"]
        record.features = [Feature(**feature) for feature in result["features"]]
    except ValueError as error:                 # our own validation messages
        record.status = "FAILED"
        record.error = str(error)
    except Exception:                           # anything GDAL could not read
        record.status = "FAILED"
        record.error = "The file could not be read as valid geospatial data."

    db.add(record)
    db.commit()
    return _file_info(record)


@app.get("/api/files/{file_id}/")
def get_file(file_id: str, db: Session = Depends(get_db)):
    return _file_info(_get_record(db, file_id))


@app.get("/api/files/{file_id}/measurements/")
def get_measurements(file_id: str, db: Session = Depends(get_db)):
    record = _get_record(db, file_id)
    if record.status != "COMPLETED":
        raise HTTPException(status_code=409, detail=f"File processing failed: {record.error}")
    return {
        "file_id": record.id,
        "feature_count": record.feature_count,
        "features": [_feature_info(feature) for feature in record.features],
    }


def _get_record(db: Session, file_id: str) -> UploadedFile:
    record = db.get(UploadedFile, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return record


def _file_info(record: UploadedFile) -> dict:
    return {
        "id": record.id,
        "filename": record.filename,
        "status": record.status,
        "crs": record.crs,
        "feature_count": record.feature_count or 0,
        "error": record.error,
    }


def _feature_info(feature: Feature) -> dict:
    return {
        "index": feature.index,
        "geometry_type": feature.geometry_type,
        "properties": feature.properties,
        "status": feature.status,
        "area_m2": feature.area_m2,
        "perimeter_m": feature.perimeter_m,
        "length_m": feature.length_m,
        "projected_crs": feature.projected_crs,
        "note": feature.note,
    }
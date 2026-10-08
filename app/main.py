from fastapi import FastAPI, File, HTTPException, UploadFile
from pathlib import Path
import shutil
import uuid

app=FastAPI(title="Geospatial File Measurement API")

@app.get("/health")
def health():
    return {"status":"ok"} 

ALLOWED_EXTENSIONS = {".kml", ".zip"}
SHAPEFILE_PARTS = {".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix"}
SHAPEFILE_MESSAGE = "Do not upload individual shapefile parts. Instead, zip all the shapefile parts into a single .zip file and upload that."
STORAGE_DIR = Path("storage")


@app.post("/api/files/",status_code=201)
def upload_file(file:UploadFile=File(...)):
    # get the extension of the file 
    extension=Path(file.filename).suffix.lower()
     

    #If it's not in ALLOWED_EXTENSIONS, raise HTTPException 400
    if extension in SHAPEFILE_PARTS:
        raise HTTPException(status_code=400, detail=SHAPEFILE_MESSAGE)

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{extension}'. Upload a .kml file, or a .zip containing a shapefile.")
    # create a file id using uuid 
    file_id=str(uuid.uuid4())
    #Make the folder STORAGE_DIR / file_id 
    (STORAGE_DIR / file_id).mkdir(parents=True, exist_ok=True)
     # 5. Open a destination file in "wb" mode and copy file.file into it 
    destination_path=STORAGE_DIR/file_id/f"uploaded{extension}"  
    with open(destination_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    #Return a dict with id and filename 
    return {"id":file_id, "filename":file.filename}
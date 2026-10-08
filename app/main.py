from fastapi import FastAPI, File, HTTPException, UploadFile
from pathlib import Path
import shutil
import uuid

app=FastAPI(title="Geospatial File Measurment API")

@app.get("/health")
def health():
    return {"status":"ok"} 

ALLOWED_EXTENSIONS = {".kml", ".zip"}
STORAGE_DIR = Path("storage")


@app.post("/api/files/",status_code=201)
def upload_file(file:UploadFile=File(...)):
    # get the extension of the file 
    extension=Path(file.filename).suffix.lower()
     

    #If it's not in ALLOWED_EXTENSIONS, raise HTTPException 400
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")
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
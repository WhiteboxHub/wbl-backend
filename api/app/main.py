
from fastapi import FastAPI, HTTPException
from models import EmployeePost
from db import fetch_batch_recordings,fetch_keyword_recordings,fetch_keyword_presentation

app = FastAPI()

@app.get("/recordings")
async def get_recordings(batch: str = None, search: str = None):
    if batch:
        recording = fetch_batch_recordings(batch)
        if recording:
            return {"recording": recording}
        else:
            raise HTTPException(status_code=404, detail="No recording found for the given batch")
    
    if search:
        recording = fetch_keyword_recordings(search)
        if recording:
            return {"recording": recording}
        else:
            raise HTTPException(status_code=404, detail="No recording found for the given name")
    
    raise HTTPException(status_code=400, detail="No valid query parameter provided")

@app.get("/presentation")
async def get_presentation(search: str = None):
    
    if search:
        presentation = fetch_keyword_presentation(search)
        if presentation:
            return {"presentation": presentation}
        else:
            raise HTTPException(status_code=404, detail="No Data found for the given name")
    
    raise HTTPException(status_code=400, detail="No valid query parameter provided")



















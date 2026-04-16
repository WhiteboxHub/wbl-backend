import uvicorn
import os
import sys

# Ensure the root directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Starting WBL Backend with Windows-safe Reloader...")
    uvicorn.run(
        "fapi.main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True,
        reload_dirs=["fapi"]
    )

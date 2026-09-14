#!/bin/bash
cd /Users/sampath/dev/wbl/wbl-backend
uvicorn fapi.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir fapi

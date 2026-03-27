import hashlib
from sqlalchemy import func, String, Text, Integer, Float, Boolean, Date, DateTime, TIMESTAMP
from sqlalchemy.orm import Session
from fastapi import Response
from sqlalchemy.types import JSON, LargeBinary

def get_model_fingerprint(db: Session, model_class) -> str:
    """
    Calculates a raw fingerprint string for a model.
    It calculates row count, max ID, max modification date, and a CRC32 checksum of all 
    relevant data columns to detect in-place manual DB updates.
    """
    try:
        mapper = model_class.__mapper__
        columns = mapper.columns

        # Determine the best 'last modified' or 'created' column
        date_columns = [c for c in columns if isinstance(c.type, (Date, DateTime, TIMESTAMP))]
        
        last_mod_col = None
        for col_name in ['last_modified', 'lastmoddatetime', 'updated_at', 'last_modified_datetime', 'last_mod_date', 'last_mod_datetime']:
            if col_name in columns:
                last_mod_col = columns[col_name]
                break
                
        # Fallback to entry_date, created_at, etc if no last_mod found
        if last_mod_col is None:
            for col_name in ['entry_date', 'created_at', 'registereddate', 'extracted_at', 'activity_date']:
                if col_name in columns:
                    last_mod_col = columns[col_name]
                    break
        
        # If still none, just pick the first date column if available
        if last_mod_col is None and date_columns:
            last_mod_col = date_columns[0]
        
        id_col = None
        pk_columns = mapper.primary_key
        if pk_columns:
            id_col = pk_columns[0]


        checksum_cols = []
        for c in columns:
            if not isinstance(c.type, (JSON, LargeBinary)):
                checksum_cols.append(func.coalesce(func.cast(c, String), ''))

        # Construct the query components
        query_components = [
            func.count().label("cnt"),
        ]
        
        if id_col is not None:
             query_components.append(func.max(id_col).label("max_id"))
        else:
             query_components.append(func.count().label("max_id"))

        if last_mod_col is not None:
            query_components.append(func.date_format(func.max(last_mod_col), '%Y-%m-%d %H:%i:%s').label("max_date"))
        else:
            query_components.append(func.count().label("max_date"))

        # Build the CRC32 checksum string aggregation
        if checksum_cols:
             query_components.append(
                 func.sum(
                     func.crc32(
                         func.concat_ws('|', *checksum_cols)
                     )
                 ).label("checksum")
             )
        else:
             query_components.append(func.count().label("checksum"))

        result = db.query(*query_components).first()

        if result and result.cnt > 0:
            cnt = result.cnt
            max_id = result.max_id if hasattr(result, 'max_id') else 0
            max_date = result.max_date if hasattr(result, 'max_date') and result.max_date else "none"
            checksum = result.checksum if hasattr(result, 'checksum') and result.checksum else 0
            
            return f"{cnt}|{max_id}|{max_date}|{checksum}"
        return "empty"

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] get_model_fingerprint failed for {model_class.__tablename__}: {e}")
        return "error"

def generate_version_for_model(db: Session, model_class) -> Response:
    """
    Dynamically generates a caching fingerprint (version hash) for a given SQLAlchemy model.
    """
    fingerprint = get_model_fingerprint(db, model_class)
    version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
    
    response = Response(status_code=200)
    response.headers["X-Data-Version"] = version_hash
    response.headers["Last-Modified"] = version_hash
    
    if "|" in fingerprint:
        response.headers["X-Total-Count"] = fingerprint.split("|")[0]
    else:
        response.headers["X-Total-Count"] = "0"
        
    return response

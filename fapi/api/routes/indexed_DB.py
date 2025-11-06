from fastapi import APIRouter
from sqlalchemy import inspect
from fapi.db.models import LeadORM
import hashlib
import json

router = APIRouter()


def get_model_schema(model):
    """
    Extracts metadata for a given SQLAlchemy ORM model.
    Returns a dict of columns with name, type, primary_key, nullable, and default.
    """
    mapper = inspect(model)
    fields = {}
    for column in mapper.columns:
        fields[column.name] = {
            "type": str(column.type),
            "primary_key": column.primary_key,
            "nullable": column.nullable,
            "default": str(column.default.arg) if column.default is not None else None
        }
    return fields


def hash_schema(data: dict) -> str:
    """
    Generates an MD5 hash of the schema dictionary.
    Used as a version identifier to detect schema changes.
    """
    json_str = json.dumps(data, sort_keys=True)
    return hashlib.md5(json_str.encode()).hexdigest()


@router.get("/schema", summary="Get all ORM model schemas")
def get_schema():
    """
    Returns the schema for all ORM models in a unified format.
    Includes a hash-based version to detect changes.
    """
    schemas = {
        "leads": get_model_schema(LeadORM)
    }

    schema_hash = hash_schema(schemas)

    return {
        "version": schema_hash,
        "tables": schemas
    }

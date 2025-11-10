from fastapi import APIRouter
from sqlalchemy import inspect
from fapi.db.models import LeadORM
import hashlib
import json

router = APIRouter()


def get_model_schema(model):
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
    json_str = json.dumps(data, sort_keys=True)
    return hashlib.md5(json_str.encode()).hexdigest()


@router.get("/schema", summary="Get all ORM model schemas")
def get_schema():
    schemas = {
        "leads": get_model_schema(LeadORM)
    }

    schema_hash = hash_schema(schemas)

    return {
        "version": schema_hash,
        "tables": schemas
    }

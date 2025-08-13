
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# ✅ Import your models here to ensure metadata is loaded
from fapi.db import models
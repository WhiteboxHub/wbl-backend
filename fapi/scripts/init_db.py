import sys
import os

# Add the parent directory to sys.path to allow importing from fapi
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fapi.db.database import engine
from fapi.db.models import Base

def init_db():
    print("Creating all tables in the database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()

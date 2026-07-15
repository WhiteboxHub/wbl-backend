from fapi.db.database import engine
from fapi.db.models import Base, CandidateAPIKeyORM
import logging

def create_tables():
    try:
        CandidateAPIKeyORM.__table__.create(bind=engine, checkfirst=True)
        logging.info("Successfully created CandidateAPIKeyORM tables")
    except Exception as e:
        logging.error(f"Error creating tables: {e}")

if __name__ == "__main__":
    create_tables()

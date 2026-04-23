from fapi.db.database import engine
from fapi.db.models import Base, CandidateResumeORM, CandidateAPIKeyORM

def create_tables():
    print("Creating tables for Candidate Setup Wizard...")
    try:
        # This will create tables if they don't exist
        CandidateResumeORM.__table__.create(bind=engine, checkfirst=True)
        CandidateAPIKeyORM.__table__.create(bind=engine, checkfirst=True)
        print("Tables created successfully (or already exist).")
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    create_tables()

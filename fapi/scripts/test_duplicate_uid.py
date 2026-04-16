from sqlalchemy import create_engine
from fapi.db.database import DATABASE_URL
from fapi.db import models
from sqlalchemy.orm import sessionmaker
import time

def test_duplicate_uid():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    uid = f"TEST_UID_{int(time.time())}"
    
    try:
        # First insert
        print(f"Inserting first record with UID: {uid}")
        file1 = models.FileApproval(
            uid=uid,
            username="testuser",
            email="test@example.com",
            drive_file_id="id1",
            original_filename="file1.pdf"
        )
        session.add(file1)
        session.commit()
        print("First record inserted successfully.")
        
        # Second insert
        print(f"Inserting second record with same UID: {uid}")
        file2 = models.FileApproval(
            uid=uid,
            username="testuser",
            email="test@example.com",
            drive_file_id="id2",
            original_filename="file2.pdf"
        )
        session.add(file2)
        session.commit()
        print("Second record inserted successfully! NO UNIQUE CONSTRAINT ERROR.")
        
        # Cleanup
        session.delete(file1)
        session.delete(file2)
        session.commit()
        
    except Exception as e:
        print(f"ERROR: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    test_duplicate_uid()

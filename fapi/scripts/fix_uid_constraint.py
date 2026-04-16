from sqlalchemy import create_engine, text
from fapi.db.database import DATABASE_URL

def fix_uid_constraint():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("Checking indexes for table 'file_approvals'...")
        result = conn.execute(text("SHOW INDEX FROM file_approvals"))
        indexes = result.fetchall()
        
        uid_index_name = None
        for idx in indexes:
            idx_dict = dict(idx._mapping)
            print(f"Found index: {idx_dict}")
            # Case insensitive check for column name
            col_name = idx_dict.get('Column_name') or idx_dict.get('column_name')
            is_unique = (idx_dict.get('Non_unique') == 0) or (idx_dict.get('non_unique') == 0)
            key_name = idx_dict.get('Key_name') or idx_dict.get('key_name')

            if col_name and col_name.lower() == 'uid' and is_unique:
                uid_index_name = key_name
                break
        
        if uid_index_name:
            if uid_index_name.upper() == 'PRIMARY':
                 print("WARNING: 'uid' is part of PRIMARY KEY. Cannot drop unique without changing PK.")
            else:
                print(f"Found unique index '{uid_index_name}' on 'uid'. Dropping it...")
                conn.execute(text(f"DROP INDEX {uid_index_name} ON file_approvals"))
                print("Successfully dropped unique index.")
        else:
            print("No unique index found on 'uid'.")
        
        # Now ensure there is a non-unique index on 'uid' for performance
        # SQLAlchemy with index=True will create one if it doesn't exist,
        # but since we might have just dropped it, let's make sure.
        print("Ensuring non-unique index exists on 'uid'...")
        try:
            conn.execute(text("CREATE INDEX ix_file_approvals_uid ON file_approvals (uid)"))
            print("Created non-unique index 'ix_file_approvals_uid'.")
        except Exception as e:
            if "Duplicate key name" in str(e) or "already exists" in str(e).lower():
                print("Non-unique index already exists.")
            else:
                print(f"Error creating index: {e}")
        
        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    fix_uid_constraint()

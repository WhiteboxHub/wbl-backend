# \



from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any, List
from datetime import datetime

from fapi.db.database import get_db
from fapi.db.schemas import (
    PlacementFeeCollectionCreate,
    PlacementFeeCollectionUpdate,
    PlacementFeeCollectionResponse,
    FeeStats
)

router = APIRouter()

# ==================== HELPER FUNCTIONS ====================

def check_table_exists(db: Session) -> bool:
    """Check if placement_fee_collection table exists"""
    try:
        result = db.execute(text("SHOW TABLES LIKE 'placement_fee_collection'"))
        return result.fetchone() is not None
    except Exception as e:
        print(f"Error checking table existence: {e}")
        return False

def get_table_columns(db: Session) -> List[str]:
    """Get all columns in placement_fee_collection table"""
    try:
        result = db.execute(text("DESCRIBE placement_fee_collection"))
        return [row[0] for row in result.fetchall()]
    except Exception as e:
        print(f"Error getting table columns: {e}")
        return []

def safe_get_column_value(row, col_name, default=None):
    """Safely get value from row dictionary"""
    try:
        return row.get(col_name, default)
    except:
        return default

# ==================== API ENDPOINTS ====================

@router.get("/candidate/placement_fees/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "status": "success",
        "message": "Placement Fee Collection API is working",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/candidate/placement_fees/simple")
async def get_simple_fees(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Simple endpoint that works even with minimal table structure
    """
    try:
        # First check if table exists
        if not check_table_exists(db):
            return {
                "page": page,
                "limit": limit,
                "total": 0,
                "total_pages": 0,
                "data": [],
                "message": "Table does not exist yet"
            }
        
        # Calculate offset
        offset = (page - 1) * limit
        
        # Get total count
        try:
            total_result = db.execute(text("SELECT COUNT(*) FROM placement_fee_collection"))
            total = total_result.scalar() or 0
        except Exception as e:
            print(f"Error counting records: {e}")
            total = 0
        
        if total == 0:
            return {
                "page": page,
                "limit": limit,
                "total": 0,
                "total_pages": 0,
                "data": [],
                "message": "No records found"
            }
        
        # Get available columns
        available_columns = get_table_columns(db)
        print(f"Available columns: {available_columns}")
        
        # Build SELECT clause based on available columns
        select_parts = []
        
        # Always include basic columns (they should exist if table was created correctly)
        basic_columns = ['id', 'placement_id', 'installment_id', 'deposit_date', 'deposit_amount', 'amount_collected', 'lastmod_user_id']
        
        for col in basic_columns:
            if col in available_columns:
                select_parts.append(f"pfc.{col}")
            else:
                select_parts.append(f"NULL as {col}")
        
        # Add optional columns if they exist
        if 'notes' in available_columns:
            select_parts.append("COALESCE(pfc.notes, '') as notes")
        else:
            select_parts.append("'' as notes")
        
        if 'last_mod_datetime' in available_columns:
            select_parts.append("COALESCE(pfc.last_mod_datetime, NOW()) as last_mod_datetime")
        else:
            select_parts.append("NOW() as last_mod_datetime")
        
        # Add joined columns (use COALESCE to handle NULLs)
        select_parts.append("COALESCE(cp.company, '') as company")
        select_parts.append("COALESCE(cp.position, '') as position")
        select_parts.append("COALESCE(c.full_name, '') as candidate_name")
        
        # Build the SQL query
        sql_query = f"""
            SELECT {', '.join(select_parts)}
            FROM placement_fee_collection pfc
            LEFT JOIN candidate_placement cp ON pfc.placement_id = cp.id
            LEFT JOIN candidate c ON cp.candidate_id = c.id
            ORDER BY pfc.id DESC
            LIMIT :limit OFFSET :offset
        """
        
        print(f"Executing query: {sql_query}")
        
        # Execute the query
        result = db.execute(text(sql_query), {"limit": limit, "offset": offset})
        
        # Safely get column names
        try:
            columns = [col[0] for col in result.cursor.description]
        except Exception as e:
            print(f"Error getting column names: {e}")
            # If we can't get column names, use defaults
            columns = ['id', 'placement_id', 'installment_id', 'deposit_date', 'deposit_amount', 
                      'amount_collected', 'lastmod_user_id', 'notes', 'last_mod_datetime',
                      'company', 'position', 'candidate_name']
        
        rows = result.fetchall()
        
        # Format data
        data = []
        for row in rows:
            row_dict = {}
            for i, col_name in enumerate(columns):
                try:
                    row_dict[col_name] = row[i]
                except IndexError:
                    row_dict[col_name] = None
            
            # Convert deposit_amount to float
            try:
                row_dict['deposit_amount'] = float(row_dict.get('deposit_amount', 0))
            except:
                row_dict['deposit_amount'] = 0.0
            
            # Ensure amount_collected is string
            row_dict['amount_collected'] = str(row_dict.get('amount_collected', 'no'))
            
            data.append(row_dict)
        
        return {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1,
            "data": data
        }
        
    except Exception as e:
        print(f"Error in get_simple_fees: {e}")
        import traceback
        traceback.print_exc()
        return {
            "page": page,
            "limit": limit,
            "total": 0,
            "total_pages": 0,
            "data": [],
            "error": str(e)
        }

@router.get("/candidate/placement_fees")
async def read_all_fee_collections(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get all placement fee collections with pagination
    """
    # Use the simple endpoint for now to ensure it works
    return await get_simple_fees(page, limit, db)

@router.get("/candidate/placement_fees/metrics", response_model=FeeStats)
async def get_fee_metrics(db: Session = Depends(get_db)):
    """
    Get fee collection statistics
    """
    try:
        # Check if table exists
        if not check_table_exists(db):
            return {
                "total_count": 0,
                "collected_count": 0,
                "pending_count": 0,
                "total_collected": 0.0,
                "total_pending": 0.0,
                "total_amount": 0.0,
                "collection_rate": 0.0
            }
        
        # Initialize default values
        metrics = {
            "total_count": 0,
            "collected_count": 0,
            "pending_count": 0,
            "total_collected": 0.0,
            "total_pending": 0.0,
            "total_amount": 0.0,
            "collection_rate": 0.0
        }
        
        try:
            # Get total count
            total_result = db.execute(text("SELECT COUNT(*) FROM placement_fee_collection"))
            metrics["total_count"] = total_result.scalar() or 0
            
            if metrics["total_count"] > 0:
                # Get collected count
                collected_result = db.execute(text(
                    "SELECT COUNT(*) FROM placement_fee_collection WHERE amount_collected = 'yes'"
                ))
                metrics["collected_count"] = collected_result.scalar() or 0
                
                # Get pending count
                pending_result = db.execute(text(
                    "SELECT COUNT(*) FROM placement_fee_collection WHERE amount_collected = 'no'"
                ))
                metrics["pending_count"] = pending_result.scalar() or 0
                
                # Get total collected amount
                collected_amount_result = db.execute(text(
                    "SELECT COALESCE(SUM(deposit_amount), 0) FROM placement_fee_collection WHERE amount_collected = 'yes'"
                ))
                metrics["total_collected"] = float(collected_amount_result.scalar() or 0)
                
                # Get total pending amount
                pending_amount_result = db.execute(text(
                    "SELECT COALESCE(SUM(deposit_amount), 0) FROM placement_fee_collection WHERE amount_collected = 'no'"
                ))
                metrics["total_pending"] = float(pending_amount_result.scalar() or 0)
                
                # Calculate total amount
                metrics["total_amount"] = metrics["total_collected"] + metrics["total_pending"]
                
                # Calculate collection rate
                if metrics["total_count"] > 0:
                    metrics["collection_rate"] = round((metrics["collected_count"] / metrics["total_count"]) * 100, 2)
                
        except Exception as query_error:
            print(f"Error in metric queries: {query_error}")
            # Return default metrics if queries fail
        
        return metrics
        
    except Exception as e:
        print(f"Error in get_fee_metrics: {e}")
        import traceback
        traceback.print_exc()
        return {
            "total_count": 0,
            "collected_count": 0,
            "pending_count": 0,
            "total_collected": 0.0,
            "total_pending": 0.0,
            "total_amount": 0.0,
            "collection_rate": 0.0
        }

@router.post("/candidate/placement_fees", 
             response_model=Dict[str, Any],
             status_code=status.HTTP_201_CREATED)
async def create_fee_collection(
    fee: PlacementFeeCollectionCreate,
    db: Session = Depends(get_db)
):
    """
    Create new fee collection
    """
    try:
        # Check if table exists, create if not
        if not check_table_exists(db):
            # Create table
            create_table_sql = """
                CREATE TABLE placement_fee_collection (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    placement_id INT NOT NULL,
                    installment_id INT NOT NULL,
                    deposit_date DATE NOT NULL,
                    deposit_amount DECIMAL(10, 2) NOT NULL,
                    amount_collected VARCHAR(3) DEFAULT 'no',
                    lastmod_user_id INT NOT NULL,
                    notes TEXT,
                    last_mod_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            db.execute(text(create_table_sql))
            db.commit()
            print("Created placement_fee_collection table")
        
        # Check if placement exists (optional - you can remove if candidate_placement doesn't exist)
        try:
            placement_result = db.execute(text("SELECT id FROM candidate_placement WHERE id = :placement_id"), 
                                         {"placement_id": fee.placement_id})
            placement_exists = placement_result.fetchone() is not None
            if not placement_exists:
                print(f"Warning: Placement ID {fee.placement_id} does not exist in candidate_placement table")
        except:
            print("Warning: Could not check placement existence (candidate_placement table might not exist)")
        
        # Check for duplicate installment
        duplicate_check = db.execute(text(
            "SELECT id FROM placement_fee_collection WHERE placement_id = :placement_id AND installment_id = :installment_id"
        ), {"placement_id": fee.placement_id, "installment_id": fee.installment_id})
        
        if duplicate_check.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Installment {fee.installment_id} already exists for placement {fee.placement_id}"
            )
        
        # Insert the new fee collection
        insert_sql = """
            INSERT INTO placement_fee_collection 
            (placement_id, installment_id, deposit_date, deposit_amount, amount_collected, lastmod_user_id, notes)
            VALUES 
            (:placement_id, :installment_id, :deposit_date, :deposit_amount, :amount_collected, :lastmod_user_id, :notes)
        """
        
        db.execute(text(insert_sql), {
            "placement_id": fee.placement_id,
            "installment_id": fee.installment_id,
            "deposit_date": fee.deposit_date,
            "deposit_amount": fee.deposit_amount,
            "amount_collected": fee.amount_collected,
            "lastmod_user_id": fee.lastmod_user_id,
            "notes": fee.notes or ""
        })
        db.commit()
        
        # Get the inserted ID
        id_result = db.execute(text("SELECT LAST_INSERT_ID()"))
        new_id = id_result.scalar()
        
        # Get the created record
        select_sql = """
            SELECT 
                id,
                placement_id,
                installment_id,
                deposit_date,
                deposit_amount,
                amount_collected,
                lastmod_user_id,
                COALESCE(notes, '') as notes,
                COALESCE(last_mod_datetime, NOW()) as last_mod_datetime
            FROM placement_fee_collection 
            WHERE id = :id
        """
        
        result = db.execute(text(select_sql), {"id": new_id})
        row = result.fetchone()
        
        if row:
            columns = [col[0] for col in result.cursor.description]
            row_dict = dict(zip(columns, row))
            
            # Try to get placement details
            try:
                placement_result = db.execute(text("""
                    SELECT cp.company, cp.position, c.full_name as candidate_name
                    FROM candidate_placement cp
                    LEFT JOIN candidate c ON cp.candidate_id = c.id
                    WHERE cp.id = :placement_id
                """), {"placement_id": fee.placement_id})
                
                placement_row = placement_result.fetchone()
                if placement_row:
                    placement_columns = [col[0] for col in placement_result.cursor.description]
                    placement_dict = dict(zip(placement_columns, placement_row))
                    row_dict.update(placement_dict)
            except:
                # If we can't get placement details, use empty values
                row_dict.update({
                    "company": "",
                    "position": "",
                    "candidate_name": ""
                })
            
            return {
                "id": row_dict.get('id'),
                "placement_id": row_dict.get('placement_id'),
                "installment_id": row_dict.get('installment_id'),
                "deposit_date": row_dict.get('deposit_date'),
                "deposit_amount": float(row_dict.get('deposit_amount', 0)),
                "amount_collected": row_dict.get('amount_collected', 'no'),
                "lastmod_user_id": row_dict.get('lastmod_user_id'),
                "notes": row_dict.get('notes', ''),
                "last_mod_datetime": row_dict.get('last_mod_datetime'),
                "company": row_dict.get('company', ''),
                "position": row_dict.get('position', ''),
                "candidate_name": row_dict.get('candidate_name', ''),
                "message": "Fee collection created successfully"
            }
        else:
            return {
                "id": new_id,
                "message": "Fee collection created but could not retrieve details"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error in create_fee_collection: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating fee collection: {str(e)}"
        )

@router.get("/candidate/placement_fees/check-table")
async def check_table_structure(db: Session = Depends(get_db)):
    """
    Check the table structure
    """
    try:
        # Check if table exists
        table_exists = check_table_exists(db)
        
        if not table_exists:
            return {
                "status": "info",
                "message": "Table 'placement_fee_collection' does not exist",
                "table_exists": False,
                "columns": [],
                "record_count": 0
            }
        
        # Get table structure
        try:
            describe_result = db.execute(text("DESCRIBE placement_fee_collection"))
            columns = []
            for row in describe_result:
                columns.append({
                    "field": row[0],
                    "type": row[1],
                    "null": row[2],
                    "key": row[3],
                    "default": row[4],
                    "extra": row[5]
                })
        except Exception as e:
            columns = []
            print(f"Error describing table: {e}")
        
        # Count records
        try:
            count_result = db.execute(text("SELECT COUNT(*) FROM placement_fee_collection"))
            record_count = count_result.scalar() or 0
        except:
            record_count = 0
        
        return {
            "status": "success",
            "table_exists": table_exists,
            "columns": columns,
            "record_count": record_count,
            "message": f"Table exists with {record_count} records and {len(columns)} columns"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "table_exists": False,
            "columns": [],
            "record_count": 0
        }

@router.post("/candidate/placement_fees/fix-table")
async def fix_table(db: Session = Depends(get_db)):
    """
    Fix the table structure by creating or repairing the table
    """
    try:
        sql_statements = [
            # Create table if it doesn't exist
            """
            CREATE TABLE IF NOT EXISTS placement_fee_collection (
                id INT AUTO_INCREMENT PRIMARY KEY,
                placement_id INT NOT NULL,
                installment_id INT NOT NULL,
                deposit_date DATE NOT NULL,
                deposit_amount DECIMAL(10, 2) NOT NULL,
                amount_collected VARCHAR(3) DEFAULT 'no',
                lastmod_user_id INT NOT NULL,
                notes TEXT,
                last_mod_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            
            # Add missing columns
            """
            ALTER TABLE placement_fee_collection 
            ADD COLUMN IF NOT EXISTS notes TEXT;
            """,
            
            """
            ALTER TABLE placement_fee_collection 
            ADD COLUMN IF NOT EXISTS last_mod_datetime TIMESTAMP 
            DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
            """
        ]
        
        for sql in sql_statements:
            db.execute(text(sql))
        
        db.commit()
        
        # Add some test data if table is empty
        count_result = db.execute(text("SELECT COUNT(*) FROM placement_fee_collection"))
        count = count_result.scalar() or 0
        
        if count == 0:
            test_data = """
            INSERT INTO placement_fee_collection 
            (placement_id, installment_id, deposit_date, deposit_amount, amount_collected, lastmod_user_id, notes)
            VALUES 
            (1, 1, '2024-01-15', 50000.00, 'yes', 1, 'First installment'),
            (1, 2, '2024-02-15', 50000.00, 'no', 1, 'Second installment pending'),
            (2, 1, '2024-01-20', 75000.00, 'yes', 1, 'Full payment'),
            (3, 1, '2024-01-25', 60000.00, 'yes', 1, 'First payment'),
            (3, 2, '2024-02-25', 40000.00, 'no', 1, 'Balance pending');
            """
            db.execute(text(test_data))
            db.commit()
        
        return {
            "status": "success",
            "message": "Table created/repaired successfully",
            "test_data_added": count == 0
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fixing table: {str(e)}"
        )

@router.get("/candidate/placement_fees/{fee_id}")
async def read_fee_collection(
    fee_id: int = Path(..., ge=1),
    db: Session = Depends(get_db)
):
    """
    Get specific fee collection by ID
    """
    try:
        if not check_table_exists(db):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fee collection table does not exist"
            )
        
        # Simple query to get the fee
        sql_query = """
            SELECT 
                id,
                placement_id,
                installment_id,
                deposit_date,
                deposit_amount,
                amount_collected,
                lastmod_user_id,
                COALESCE(notes, '') as notes,
                COALESCE(last_mod_datetime, NOW()) as last_mod_datetime
            FROM placement_fee_collection 
            WHERE id = :fee_id
        """
        
        result = db.execute(text(sql_query), {"fee_id": fee_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fee collection not found"
            )
        
        columns = [col[0] for col in result.cursor.description]
        row_dict = dict(zip(columns, row))
        
        return {
            "id": row_dict.get('id'),
            "placement_id": row_dict.get('placement_id'),
            "installment_id": row_dict.get('installment_id'),
            "deposit_date": row_dict.get('deposit_date'),
            "deposit_amount": float(row_dict.get('deposit_amount', 0)),
            "amount_collected": row_dict.get('amount_collected', 'no'),
            "lastmod_user_id": row_dict.get('lastmod_user_id'),
            "notes": row_dict.get('notes', ''),
            "last_mod_datetime": row_dict.get('last_mod_datetime')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in read_fee_collection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching fee collection: {str(e)}"
        )

# Health check endpoint
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "placement_fee_collection",
        "timestamp": datetime.now().isoformat()
    }
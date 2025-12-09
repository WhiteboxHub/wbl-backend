# fapi/db/utils.py


from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import logging

# Import models and schemas
from fapi.db.models import PlacementFeeCollectionORM, CandidatePlacementORM, CandidateORM
from fapi.db import schemas

logger = logging.getLogger(__name__)

# ============================================
# PLACEMENT FEE COLLECTION CRUD OPERATIONS
# ============================================

def get_all_fee_collections(db: Session, skip: int = 0, limit: int = 100) -> List[PlacementFeeCollectionORM]:
    """
    Get all fee collections with pagination
    """
    try:
        return db.query(PlacementFeeCollectionORM)\
            .order_by(PlacementFeeCollectionORM.id.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    except Exception as e:
        logger.error(f"Error getting all fee collections: {e}")
        raise

def get_fee_collection(db: Session, fee_id: int) -> Optional[PlacementFeeCollectionORM]:
    """
    Get a specific fee collection by ID
    """
    try:
        return db.query(PlacementFeeCollectionORM)\
            .filter(PlacementFeeCollectionORM.id == fee_id)\
            .first()
    except Exception as e:
        logger.error(f"Error getting fee collection {fee_id}: {e}")
        raise

def get_fee_collections_by_placement(
    db: Session, 
    placement_id: int, 
    skip: int = 0, 
    limit: int = 100
) -> List[PlacementFeeCollectionORM]:
    """
    Get all fee collections for a specific placement
    """
    try:
        return db.query(PlacementFeeCollectionORM)\
            .filter(PlacementFeeCollectionORM.placement_id == placement_id)\
            .order_by(PlacementFeeCollectionORM.installment_id.asc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    except Exception as e:
        logger.error(f"Error getting fee collections for placement {placement_id}: {e}")
        raise

def get_fee_collections_by_filters(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    placement_id: Optional[int] = None,
    amount_collected: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    installment_id: Optional[int] = None,
    lastmod_user_id: Optional[int] = None
) -> List[PlacementFeeCollectionORM]:
    """
    Get fee collections with various filters
    """
    try:
        query = db.query(PlacementFeeCollectionORM)
        
        # Apply filters if provided
        if placement_id:
            query = query.filter(PlacementFeeCollectionORM.placement_id == placement_id)
        
        if amount_collected:
            query = query.filter(PlacementFeeCollectionORM.amount_collected == amount_collected)
        
        if start_date:
            query = query.filter(PlacementFeeCollectionORM.deposit_date >= start_date)
        
        if end_date:
            query = query.filter(PlacementFeeCollectionORM.deposit_date <= end_date)
        
        if installment_id:
            query = query.filter(PlacementFeeCollectionORM.installment_id == installment_id)
        
        if lastmod_user_id:
            query = query.filter(PlacementFeeCollectionORM.lastmod_user_id == lastmod_user_id)
        
        # Order by deposit date (newest first) and ID
        return query.order_by(
            PlacementFeeCollectionORM.deposit_date.desc(),
            PlacementFeeCollectionORM.id.desc()
        ).offset(skip).limit(limit).all()
        
    except Exception as e:
        logger.error(f"Error filtering fee collections: {e}")
        raise

def search_fee_collections(
    db: Session,
    search_term: str,
    skip: int = 0,
    limit: int = 100
) -> List[PlacementFeeCollectionORM]:
    """
    Search fee collections by notes or amount
    """
    try:
        return db.query(PlacementFeeCollectionORM)\
            .filter(
                and_(
                    PlacementFeeCollectionORM.notes.ilike(f"%{search_term}%")
                )
            )\
            .order_by(PlacementFeeCollectionORM.id.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    except Exception as e:
        logger.error(f"Error searching fee collections: {e}")
        raise

def create_fee_collection(db: Session, fee: schemas.PlacementFeeCollectionCreate) -> PlacementFeeCollectionORM:
    """
    Create a new fee collection
    """
    try:
        # Check if placement exists
        placement = db.query(CandidatePlacementORM)\
            .filter(CandidatePlacementORM.id == fee.placement_id)\
            .first()
        
        if not placement:
            raise ValueError(f"Placement with ID {fee.placement_id} not found")
        
        # Create new fee collection
        db_fee = PlacementFeeCollectionORM(
            placement_id=fee.placement_id,
            installment_id=fee.installment_id,
            deposit_date=fee.deposit_date,
            deposit_amount=fee.deposit_amount,
            amount_collected=fee.amount_collected.value,  # Convert enum to string
            lastmod_user_id=fee.lastmod_user_id,
            notes=fee.notes
        )
        
        db.add(db_fee)
        db.commit()
        db.refresh(db_fee)
        
        logger.info(f"Created fee collection with ID {db_fee.id}")
        return db_fee
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating fee collection: {e}")
        raise

def update_fee_collection(
    db: Session, 
    fee_id: int, 
    fee_update: schemas.PlacementFeeCollectionUpdate
) -> Optional[PlacementFeeCollectionORM]:
    """
    Update an existing fee collection
    """
    try:
        db_fee = get_fee_collection(db, fee_id)
        if not db_fee:
            return None
        
        # Get update data, excluding unset fields
        update_data = fee_update.model_dump(exclude_unset=True)
        
        # Handle enum conversion if amount_collected is being updated
        if 'amount_collected' in update_data and update_data['amount_collected']:
            update_data['amount_collected'] = update_data['amount_collected'].value
        
        # Update fields
        for field, value in update_data.items():
            if value is not None:
                setattr(db_fee, field, value)
        
        db.commit()
        db.refresh(db_fee)
        
        logger.info(f"Updated fee collection with ID {fee_id}")
        return db_fee
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating fee collection {fee_id}: {e}")
        raise

def delete_fee_collection(db: Session, fee_id: int) -> bool:
    """
    Delete a fee collection
    """
    try:
        db_fee = get_fee_collection(db, fee_id)
        if not db_fee:
            return False
        
        db.delete(db_fee)
        db.commit()
        
        logger.info(f"Deleted fee collection with ID {fee_id}")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting fee collection {fee_id}: {e}")
        raise

# ============================================
# STATISTICS AND ANALYTICS FUNCTIONS
# ============================================

def get_fee_stats(db: Session) -> Dict[str, Any]:
    """
    Get fee collection statistics
    """
    try:
        # Count totals
        total_count = db.query(PlacementFeeCollectionORM).count()
        
        # Count by status
        collected_count = db.query(PlacementFeeCollectionORM)\
            .filter(PlacementFeeCollectionORM.amount_collected == "yes")\
            .count()
        
        pending_count = db.query(PlacementFeeCollectionORM)\
            .filter(PlacementFeeCollectionORM.amount_collected == "no")\
            .count()
        
        # Sum amounts
        total_collected_result = db.query(func.sum(PlacementFeeCollectionORM.deposit_amount))\
            .filter(PlacementFeeCollectionORM.amount_collected == "yes")\
            .scalar()
        
        total_pending_result = db.query(func.sum(PlacementFeeCollectionORM.deposit_amount))\
            .filter(PlacementFeeCollectionORM.amount_collected == "no")\
            .scalar()
        
        # Handle None values
        total_collected = total_collected_result if total_collected_result else Decimal('0')
        total_pending = total_pending_result if total_pending_result else Decimal('0')
        
        return {
            "total_count": total_count,
            "collected_count": collected_count,
            "pending_count": pending_count,
            "total_collected": float(total_collected),
            "total_pending": float(total_pending),
            "total_amount": float(total_collected + total_pending),
            "collection_rate": float(collected_count / total_count * 100) if total_count > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting fee stats: {e}")
        raise

def get_fee_stats_by_date_range(
    db: Session, 
    start_date: date, 
    end_date: date
) -> Dict[str, Any]:
    """
    Get fee collection statistics for a date range
    """
    try:
        # Count totals in date range
        total_count = db.query(PlacementFeeCollectionORM)\
            .filter(
                PlacementFeeCollectionORM.deposit_date >= start_date,
                PlacementFeeCollectionORM.deposit_date <= end_date
            )\
            .count()
        
        # Count collected in date range
        collected_count = db.query(PlacementFeeCollectionORM)\
            .filter(
                PlacementFeeCollectionORM.deposit_date >= start_date,
                PlacementFeeCollectionORM.deposit_date <= end_date,
                PlacementFeeCollectionORM.amount_collected == "yes"
            )\
            .count()
        
        # Sum amounts in date range
        total_collected_result = db.query(func.sum(PlacementFeeCollectionORM.deposit_amount))\
            .filter(
                PlacementFeeCollectionORM.deposit_date >= start_date,
                PlacementFeeCollectionORM.deposit_date <= end_date,
                PlacementFeeCollectionORM.amount_collected == "yes"
            )\
            .scalar()
        
        total_pending_result = db.query(func.sum(PlacementFeeCollectionORM.deposit_amount))\
            .filter(
                PlacementFeeCollectionORM.deposit_date >= start_date,
                PlacementFeeCollectionORM.deposit_date <= end_date,
                PlacementFeeCollectionORM.amount_collected == "no"
            )\
            .scalar()
        
        # Handle None values
        total_collected = total_collected_result if total_collected_result else Decimal('0')
        total_pending = total_pending_result if total_pending_result else Decimal('0')
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "total_count": total_count,
            "collected_count": collected_count,
            "pending_count": total_count - collected_count,
            "total_collected": float(total_collected),
            "total_pending": float(total_pending),
            "total_amount": float(total_collected + total_pending)
        }
        
    except Exception as e:
        logger.error(f"Error getting fee stats by date range: {e}")
        raise

def get_fee_stats_by_placement(db: Session, placement_id: int) -> Dict[str, Any]:
    """
    Get fee collection statistics for a specific placement
    """
    try:
        # Get all fees for this placement
        fees = get_fee_collections_by_placement(db, placement_id)
        
        # Calculate stats
        total_count = len(fees)
        collected_count = sum(1 for fee in fees if fee.amount_collected == "yes")
        total_collected = sum(fee.deposit_amount for fee in fees if fee.amount_collected == "yes")
        total_pending = sum(fee.deposit_amount for fee in fees if fee.amount_collected == "no")
        
        return {
            "placement_id": placement_id,
            "total_count": total_count,
            "collected_count": collected_count,
            "pending_count": total_count - collected_count,
            "total_collected": float(total_collected),
            "total_pending": float(total_pending),
            "total_amount": float(total_collected + total_pending),
            "installments": [
                {
                    "installment_id": fee.installment_id,
                    "deposit_date": fee.deposit_date,
                    "amount": float(fee.deposit_amount),
                    "status": fee.amount_collected,
                    "notes": fee.notes
                }
                for fee in sorted(fees, key=lambda x: x.installment_id)
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting fee stats for placement {placement_id}: {e}")
        raise

# ============================================
# VALIDATION AND HELPER FUNCTIONS
# ============================================

def validate_fee_collection_data(db: Session, fee_data: dict) -> List[str]:
    """
    Validate fee collection data and return list of errors
    """
    errors = []
    
    # Check required fields
    required_fields = ['placement_id', 'installment_id', 'deposit_date', 'deposit_amount', 'lastmod_user_id']
    for field in required_fields:
        if field not in fee_data or fee_data[field] is None:
            errors.append(f"{field} is required")
    
    # Check placement exists
    if 'placement_id' in fee_data and fee_data['placement_id']:
        placement = db.query(CandidatePlacementORM)\
            .filter(CandidatePlacementORM.id == fee_data['placement_id'])\
            .first()
        if not placement:
            errors.append(f"Placement with ID {fee_data['placement_id']} does not exist")
    
    # Validate amount
    if 'deposit_amount' in fee_data and fee_data['deposit_amount']:
        try:
            amount = Decimal(str(fee_data['deposit_amount']))
            if amount <= 0:
                errors.append("Deposit amount must be greater than 0")
        except:
            errors.append("Invalid deposit amount format")
    
    # Validate installment_id is positive
    if 'installment_id' in fee_data and fee_data['installment_id']:
        if fee_data['installment_id'] <= 0:
            errors.append("Installment ID must be greater than 0")
    
    return errors

def get_next_installment_number(db: Session, placement_id: int) -> int:
    """
    Get the next installment number for a placement
    """
    try:
        last_installment = db.query(func.max(PlacementFeeCollectionORM.installment_id))\
            .filter(PlacementFeeCollectionORM.placement_id == placement_id)\
            .scalar()
        
        return (last_installment or 0) + 1
    except Exception as e:
        logger.error(f"Error getting next installment number for placement {placement_id}: {e}")
        return 1

def check_duplicate_fee_collection(
    db: Session, 
    placement_id: int, 
    installment_id: int, 
    exclude_id: Optional[int] = None
) -> bool:
    """
    Check if a fee collection with same placement and installment already exists
    """
    try:
        query = db.query(PlacementFeeCollectionORM)\
            .filter(
                PlacementFeeCollectionORM.placement_id == placement_id,
                PlacementFeeCollectionORM.installment_id == installment_id
            )
        
        if exclude_id:
            query = query.filter(PlacementFeeCollectionORM.id != exclude_id)
        
        return query.first() is not None
    except Exception as e:
        logger.error(f"Error checking duplicate fee collection: {e}")
        return False

# ============================================
# BULK OPERATIONS
# ============================================

def bulk_create_fee_collections(
    db: Session, 
    fees: List[schemas.PlacementFeeCollectionCreate]
) -> List[PlacementFeeCollectionORM]:
    """
    Create multiple fee collections in bulk
    """
    created_fees = []
    try:
        for fee_data in fees:
            # Create each fee collection
            db_fee = PlacementFeeCollectionORM(
                placement_id=fee_data.placement_id,
                installment_id=fee_data.installment_id,
                deposit_date=fee_data.deposit_date,
                deposit_amount=fee_data.deposit_amount,
                amount_collected=fee_data.amount_collected.value,
                lastmod_user_id=fee_data.lastmod_user_id,
                notes=fee_data.notes
            )
            db.add(db_fee)
            created_fees.append(db_fee)
        
        db.commit()
        
        # Refresh all created fees
        for fee in created_fees:
            db.refresh(fee)
        
        logger.info(f"Bulk created {len(created_fees)} fee collections")
        return created_fees
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk create fee collections: {e}")
        raise

def bulk_update_fee_collections(
    db: Session, 
    updates: List[Dict[str, Any]]
) -> List[PlacementFeeCollectionORM]:
    """
    Update multiple fee collections in bulk
    """
    updated_fees = []
    try:
        for update_data in updates:
            fee_id = update_data.get('id')
            if not fee_id:
                continue
            
            fee_update = schemas.PlacementFeeCollectionUpdate(**update_data)
            updated_fee = update_fee_collection(db, fee_id, fee_update)
            if updated_fee:
                updated_fees.append(updated_fee)
        
        logger.info(f"Bulk updated {len(updated_fees)} fee collections")
        return updated_fees
        
    except Exception as e:
        logger.error(f"Error in bulk update fee collections: {e}")
        raise

# ============================================
# EXPORT AND REPORT FUNCTIONS
# ============================================

def get_fee_collections_for_export(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    placement_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get fee collections data formatted for export (CSV/Excel)
    """
    try:
        # Build query
        query = db.query(
            PlacementFeeCollectionORM,
            CandidatePlacementORM,
            CandidateORM
        ).join(
            CandidatePlacementORM,
            PlacementFeeCollectionORM.placement_id == CandidatePlacementORM.id
        ).join(
            CandidateORM,
            CandidatePlacementORM.candidate_id == CandidateORM.id
        )
        
        # Apply filters
        if start_date:
            query = query.filter(PlacementFeeCollectionORM.deposit_date >= start_date)
        
        if end_date:
            query = query.filter(PlacementFeeCollectionORM.deposit_date <= end_date)
        
        if placement_id:
            query = query.filter(PlacementFeeCollectionORM.placement_id == placement_id)
        
        results = query.order_by(
            PlacementFeeCollectionORM.deposit_date.desc(),
            PlacementFeeCollectionORM.id.desc()
        ).all()
        
        # Format results for export
        export_data = []
        for fee, placement, candidate in results:
            export_data.append({
                'fee_id': fee.id,
                'placement_id': fee.placement_id,
                'candidate_name': getattr(candidate, 'name', 'Unknown'),
                'company': placement.company,
                'position': placement.position,
                'installment_id': fee.installment_id,
                'deposit_date': fee.deposit_date,
                'deposit_amount': float(fee.deposit_amount),
                'amount_collected': fee.amount_collected,
                'status': 'Collected' if fee.amount_collected == 'yes' else 'Pending',
                'lastmod_user_id': fee.lastmod_user_id,
                'notes': fee.notes or '',
                'last_modified': fee.last_mod_datetime
            })
        
        return export_data
        
    except Exception as e:
        logger.error(f"Error getting fee collections for export: {e}")
        raise

# ============================================
# UTILITY FUNCTIONS FOR FRONTEND
# ============================================

def get_fee_collection_with_details(db: Session, fee_id: int) -> Optional[Dict[str, Any]]:
    """
    Get fee collection with placement and candidate details
    """
    try:
        fee = db.query(PlacementFeeCollectionORM)\
            .filter(PlacementFeeCollectionORM.id == fee_id)\
            .first()
        
        if not fee:
            return None
        
        # Get placement details
        placement = db.query(CandidatePlacementORM)\
            .filter(CandidatePlacementORM.id == fee.placement_id)\
            .first()
        
        result = {
            **fee.__dict__,
            'placement': None,
            'candidate': None
        }
        
        if placement:
            result['placement'] = {
                'company': placement.company,
                'position': placement.position,
                'placement_date': placement.placement_date,
                'status': placement.status
            }
            
            # Get candidate details
            candidate = db.query(CandidateORM)\
                .filter(CandidateORM.id == placement.candidate_id)\
                .first()
            
            if candidate:
                result['candidate'] = {
                    'id': candidate.id,
                    'name': getattr(candidate, 'name', 'Unknown'),
                    'email': getattr(candidate, 'email', None)
                }
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting fee collection with details {fee_id}: {e}")
        raise

def get_fee_collections_summary(
    db: Session,
    group_by: str = 'month'  # 'month', 'year', 'placement', 'status'
) -> List[Dict[str, Any]]:
    """
    Get summary of fee collections grouped by different criteria
    """
    try:
        if group_by == 'month':
            # Group by month
            results = db.query(
                func.date_format(PlacementFeeCollectionORM.deposit_date, '%Y-%m').label('month'),
                func.count(PlacementFeeCollectionORM.id).label('count'),
                func.sum(PlacementFeeCollectionORM.deposit_amount).label('total_amount')
            ).group_by('month')\
             .order_by('month')\
             .all()
            
            return [
                {
                    'group': row.month,
                    'count': row.count,
                    'total_amount': float(row.total_amount) if row.total_amount else 0.0
                }
                for row in results
            ]
            
        elif group_by == 'status':
            # Group by collection status
            results = db.query(
                PlacementFeeCollectionORM.amount_collected.label('status'),
                func.count(PlacementFeeCollectionORM.id).label('count'),
                func.sum(PlacementFeeCollectionORM.deposit_amount).label('total_amount')
            ).group_by('status')\
             .all()
            
            return [
                {
                    'group': row.status,
                    'count': row.count,
                    'total_amount': float(row.total_amount) if row.total_amount else 0.0
                }
                for row in results
            ]
        
        elif group_by == 'placement':
            # Group by placement
            results = db.query(
                PlacementFeeCollectionORM.placement_id.label('placement_id'),
                func.count(PlacementFeeCollectionORM.id).label('count'),
                func.sum(PlacementFeeCollectionORM.deposit_amount).label('total_amount')
            ).group_by('placement_id')\
             .order_by(func.sum(PlacementFeeCollectionORM.deposit_amount).desc())\
             .limit(10)\
             .all()
            
            return [
                {
                    'group': f"Placement {row.placement_id}",
                    'placement_id': row.placement_id,
                    'count': row.count,
                    'total_amount': float(row.total_amount) if row.total_amount else 0.0
                }
                for row in results
            ]
        
        else:
            raise ValueError(f"Invalid group_by value: {group_by}")
            
    except Exception as e:
        logger.error(f"Error getting fee collections summary: {e}")
        raise







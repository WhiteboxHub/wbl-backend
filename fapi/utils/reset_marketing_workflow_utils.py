import sys
from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from fapi.db.models import AutomationWorkflowORM, AutomationWorkflowScheduleORM, AutomationWorkflowLogORM
from fapi.utils.weekly_marketing_report_workflow_utils import ensure_weekly_marketing_report_workflow

def reset_marketing_workflow():
    db = SessionLocal()
    try:
        print("Starting reset of 'weekly_marketing_report' workflow...")
        
        # 1. Find the workflow
        workflow = db.query(AutomationWorkflowORM).filter(
            AutomationWorkflowORM.workflow_key == "weekly_marketing_report"
        ).first()
        
        if workflow:
            print(f"Found workflow ID: {workflow.id}. Deleting related schedules and logs...")
            
            # 2. Delete related logs and schedules
            db.query(AutomationWorkflowLogORM).filter(AutomationWorkflowLogORM.workflow_id == workflow.id).delete()
            db.query(AutomationWorkflowScheduleORM).filter(AutomationWorkflowScheduleORM.automation_workflow_id == workflow.id).delete()
            
            # 3. Delete the workflow itself
            db.delete(workflow)
            db.commit()
            print("Successfully deleted old workflow, schedules, and logs.")
        else:
            print("No existing workflow found with key 'weekly_marketing_report'.")
            
        # 4. Re-create using the official ensure function
        print("Re-creating workflow and daily schedule...")
        result = ensure_weekly_marketing_report_workflow(db)
        print(f"Result: {result}")
        
        db.commit()
        print("\nReset complete! The report is now scheduled for 8:00 AM PST (15:00 UTC) daily.")
        print("It will NOT run again today because the next_run_at has been reset to tomorrow.")
        
    except Exception as e:
        db.rollback()
        print(f"Error during reset: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_marketing_workflow()

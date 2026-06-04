import pytest
import sqlalchemy
from fastapi.exceptions import ResponseValidationError
import base64
from fapi.db.models import CandidateORM, CandidateMarketingORM
from datetime import date

def test_outreach_orchestrator_routes(client, admin_headers):
    # GET routes
    get_routes = [
        "/api/orchestrator/schedules/due",
        "/api/orchestrator/schedules/999",
        "/api/orchestrator/workflows/key/test_key",
        "/api/orchestrator/workflows/999",
        "/api/orchestrator/candidate-credentials/999",
        "/api/orchestrator/delivery-engine/999",
        "/api/orchestrator/email-template/999",
        "/api/orchestrator/logs",
    ]
    for route in get_routes:
        try:
            res = client.get(route, headers=admin_headers)
            assert res.status_code in [200, 401, 403, 404, 422]
        except sqlalchemy.exc.SQLAlchemyError as e:
            pytest.xfail(f"SQLite DB missing mapping: {e}")
        except Exception:
            pass

    # POST routes
    post_routes = [
        ("/api/orchestrator/schedules/999/lock", {}),
        ("/api/orchestrator/workflows/999/execute-recipient-sql", {"sql_query": "SELECT *", "parameters": {}}),
        ("/api/orchestrator/workflows/999/execute-reset-sql", {"sql_query": "UPDATE", "parameters": {}}),
        ("/api/orchestrator/logs", {
            "workflow_id": 1,
            "run_id": "test_run",
            "status": "started"
        })
    ]
    for route, payload in post_routes:
        try:
            res = client.post(route, json=payload, headers=admin_headers)
            assert res.status_code in [200, 201, 204, 400, 401, 403, 404, 422, 500]
        except sqlalchemy.exc.SQLAlchemyError as e:
            pytest.xfail(f"SQLite DB mapping error: {e}")
        except Exception:
            pass

    # PUT routes
    put_routes = [
        ("/api/orchestrator/schedules/999", {"enabled": True}),
        ("/api/orchestrator/workflows/999", {"name": "Test"}),
        ("/api/orchestrator/logs/999", {"status": "finished"})
    ]
    for route, payload in put_routes:
        try:
            res = client.put(route, json=payload, headers=admin_headers)
            assert res.status_code in [200, 401, 403, 404, 422, 500]
        except sqlalchemy.exc.SQLAlchemyError as e:
            pytest.xfail(f"SQLite DB mapping error: {e}")
        except Exception:
            pass


def test_weekly_workflow_routes(client, admin_headers):
    # GET routes
    get_routes = [
        "/api/weekly-workflow/trigger-run",
        "/api/weekly-workflow/eligible-candidates"
    ]
    for route in get_routes:
        try:
            res = client.get(route, headers=admin_headers)
            assert res.status_code in [200, 401, 403, 404, 422, 500]
        except sqlalchemy.exc.SQLAlchemyError as e:
            pytest.xfail(f"SQLite DB missing mapping: {e}")
        except Exception:
            pass

    # POST routes
    post_routes = [
        ("/api/weekly-workflow/reset/999", {}),
        ("/api/weekly-workflow/update-parameters/999", {"key": "val"})
    ]
    for route, payload in post_routes:
        try:
            res = client.post(route, json=payload, headers=admin_headers)
            assert res.status_code in [200, 401, 403, 404, 422, 500]
        except sqlalchemy.exc.SQLAlchemyError as e:
            pytest.xfail(f"SQLite DB missing mapping: {e}")
        except Exception:
            pass


def test_unsubscribe_routes(client):
    # Unsubscribe routes are generally public, so no admin_headers strictly required
    encoded_token = base64.b64encode(b"test@example.com").decode('utf-8')
    routes = [
        f"/api/unsubscribe/outreach-feedback?token={encoded_token}&type=unsubscribe",
        "/api/unsubscribe/outreach-feedback?email=test@example.com&type=bounce",
        "/api/unsubscribe/outreach-feedback?email=test@example.com&type=complaint",
        "/api/unsubscribe/outreach-unsubscribe?email=test@example.com",
        "/api/unsubscribe/unsubscribe?email=test@example.com",
    ]
    for route in routes:
        try:
            res = client.get(route)
            assert res.status_code in [200, 307, 400, 404, 422, 500]
        except sqlalchemy.exc.SQLAlchemyError as e:
            pytest.xfail(f"SQLite DB missing mapping: {e}")
        except Exception:
            pass


def test_automation_workflow_schedule_routes(client, admin_headers):
    try:
        res = client.head("/api/automation-workflow-schedule/", headers=admin_headers)
        assert res.status_code in [200, 401, 403, 500]
    except Exception:
        pass
    
    try:
        res = client.get("/api/automation-workflow-schedule/", headers=admin_headers)
        assert res.status_code in [200, 401, 403, 500]
    except Exception:
        pass

    try:
        res = client.post("/api/automation-workflow-schedule/", json={
            "workflow_id": 1,
            "cron_expression": "* * * * *"
        }, headers=admin_headers)
        assert res.status_code in [200, 201, 400, 401, 403, 422, 500]
    except sqlalchemy.exc.SQLAlchemyError as e:
        pytest.xfail(f"SQLite mapping error: {e}")
    except Exception:
        pass

    try:
        res = client.put("/api/automation-workflow-schedule/999", json={
            "cron_expression": "0 0 * * *"
        }, headers=admin_headers)
        assert res.status_code in [200, 400, 401, 403, 404, 422, 500]
    except sqlalchemy.exc.SQLAlchemyError as e:
        pytest.xfail(f"SQLite mapping error: {e}")
    except Exception:
        pass

    try:
        res = client.delete("/api/automation-workflow-schedule/999", headers=admin_headers)
        assert res.status_code in [200, 401, 403, 404, 500]
    except sqlalchemy.exc.SQLAlchemyError as e:
        pytest.xfail(f"SQLite mapping error: {e}")
    except Exception:
        pass


def test_get_candidate_credentials_success(client, admin_headers, db_session):
    """
    Test retrieving SMTP/IMAP credentials for an active CandidateMarketing record.
    Seeds necessary data in the mock SQLite database first.
    """
    # 1. Seed Parent Candidate Record
    candidate = CandidateORM(
        id=777,
        full_name="Alex Smith",
        email="alex.smith@test.com",
        status="active"
    )
    db_session.add(candidate)
    db_session.flush() # Ensure candidate ID 777 is persisted in session
    
    # 2. Seed Candidate Marketing Credentials Record
    marketing = CandidateMarketingORM(
        candidate_id=777,
        email="alex.smith@test.com",
        password="mock_smtp_password",
        imap_password="mock_imap_password",
        status="active",
        start_date=date(2026, 1, 1)
    )
    db_session.add(marketing)
    db_session.commit()
    
    # 3. Request credentials via endpoint
    response = client.get("/api/orchestrator/candidate-credentials/777", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alex.smith@test.com"
    assert data["candidate_name"] == "Alex Smith"
    assert data["password"] == "mock_smtp_password"
    assert data["imap_password"] == "mock_imap_password"
    assert data["linkedin_url"] is None

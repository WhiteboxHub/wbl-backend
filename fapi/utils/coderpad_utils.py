"""
CodePad Utilities
Handles database operations and orchestration for code snippets and execution.

Database access: all queries use the SQLAlchemy ORM (``Session.query``, filters,
``in_()``, ``ilike()`` with bound parameters). There is no string-concatenated SQL
or ``text()`` raw fragments here, so user input is not interpolated into query text.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func as sa_func
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from fapi.db.models import CodeSnippetORM, CodeExecutionLogORM, CoderpadQuestionORM, AuthUserORM, CandidateORM
from fapi.db.schemas import (
    CodeSnippetCreate,
    CodeSnippetUpdate,
    CodeExecutionRequest,
    CodeExecutionWithTestsResponse,
    TestCaseExecutionResult,
    TestCase,
    CoderpadQuestionCreate,
    CoderpadQuestionUpdate,
)
from fapi.utils.code_execution_utils import CodeExecutor
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# Limits for assignable-candidate search (defense in depth; ORM still binds values)
MAX_ASSIGNABLE_SEARCH_LEN = 200


def _sanitize_search_term(raw: Optional[str]) -> Optional[str]:
    """Normalize search input: strip, drop NULs, cap length. Returns None if empty."""
    if raw is None:
        return None
    t = raw.replace("\x00", "").strip()
    if not t:
        return None
    return t[:MAX_ASSIGNABLE_SEARCH_LEN]


# ==================== Code Snippet CRUD ====================

def get_user_snippets(db: Session, user_id: int) -> List[CodeSnippetORM]:
    """Get all code snippets for a user"""
    return db.query(CodeSnippetORM).filter(
        CodeSnippetORM.authuser_id == user_id
    ).order_by(CodeSnippetORM.updated_at.desc()).all()


def get_snippet_by_id(db: Session, snippet_id: int, user_id: int) -> Optional[CodeSnippetORM]:
    """Get a specific code snippet by ID (verify ownership)"""
    return db.query(CodeSnippetORM).filter(
        and_(
            CodeSnippetORM.id == snippet_id,
            CodeSnippetORM.authuser_id == user_id
        )
    ).first()


def create_snippet(
    db: Session,
    user_id: int,
    snippet_data: CodeSnippetCreate
) -> CodeSnippetORM:
    """Create a new code snippet"""
    # Convert test_cases to JSON for storage
    test_cases_json = None
    if snippet_data.test_cases:
        test_cases_json = [tc.model_dump() for tc in snippet_data.test_cases]

    db_snippet = CodeSnippetORM(
        authuser_id=user_id,
        title=snippet_data.title,
        description=snippet_data.description,
        language=snippet_data.language,
        code=snippet_data.code,
        test_cases=test_cases_json,
        execution_timeout=snippet_data.execution_timeout,
        is_shared=snippet_data.is_shared,
        shared_with=snippet_data.shared_with,
    )
    
    db.add(db_snippet)
    db.commit()
    db.refresh(db_snippet)
    
    logger.info(f"Created code snippet {db_snippet.id} for user {user_id}")
    return db_snippet


def update_snippet(
    db: Session,
    snippet: CodeSnippetORM,
    snippet_data: CodeSnippetUpdate
) -> CodeSnippetORM:
    """Update a code snippet"""
    update_data = snippet_data.model_dump(exclude_unset=True)
    
    # Handle test_cases special conversion
    if "test_cases" in update_data and update_data["test_cases"]:
        update_data["test_cases"] = [tc.model_dump() for tc in update_data["test_cases"]]
    
    for key, value in update_data.items():
        setattr(snippet, key, value)
    
    db.commit()
    db.refresh(snippet)
    
    logger.info(f"Updated code snippet {snippet.id}")
    return snippet


def delete_snippet(db: Session, snippet: CodeSnippetORM) -> None:
    """Delete a code snippet and its execution logs"""
    snippet_id = snippet.id
    
    # Delete associated execution logs
    db.query(CodeExecutionLogORM).filter(
        CodeExecutionLogORM.code_snippet_id == snippet_id
    ).delete()
    
    # Delete the snippet
    db.delete(snippet)
    db.commit()
    
    logger.info(f"Deleted code snippet {snippet_id}")


# ==================== Code Execution ====================

def run_test_cases_against_code(
    code: str,
    language: str,
    timeout: int,
    test_cases_data: Any,
) -> Optional[List[TestCaseExecutionResult]]:
    """Run optional stdin tests against code (same logic as saved snippets)."""
    if not test_cases_data:
        return None
    if isinstance(test_cases_data, str):
        test_cases_data = json.loads(test_cases_data)
    test_results: List[TestCaseExecutionResult] = []
    for idx, test_case_data in enumerate(test_cases_data):
        test_case = TestCase(**test_case_data)
        test_result = CodeExecutor.execute(
            code=code,
            language=language,
            input_data=test_case.input,
            timeout=timeout,
        )
        actual_output = test_result.get("output", "").strip() if test_result.get("output") else None
        expected_output = test_case.expected_output.strip()
        passed = actual_output == expected_output if actual_output is not None else False
        test_results.append(
            TestCaseExecutionResult(
                test_case_index=idx,
                input=test_case.input,
                expected=expected_output,
                actual=actual_output,
                error=test_result.get("error"),
                passed=passed,
            )
        )
    return test_results


def execute_code_direct(
    db: Session,
    user_id: int,
    request: CodeExecutionRequest
) -> CodeExecutionWithTestsResponse:
    """Execute code directly without saving; optional test_cases run like snippet execute."""
    result = CodeExecutor.execute(
        code=request.code,
        language=request.language,
        input_data=request.input_data,
        timeout=request.timeout,
    )

    test_results = None
    tc_payload = request.test_cases
    if tc_payload:
        tc_json = [tc.model_dump() for tc in tc_payload]
        test_results = run_test_cases_against_code(
            request.code,
            request.language,
            request.timeout,
            tc_json,
        )

    log_entry = CodeExecutionLogORM(
        code_snippet_id=None,
        authuser_id=user_id,
        language=request.language,
        code_executed=request.code[:5000],
        input_data=request.input_data[:1000] if request.input_data else None,
        output=result.get("output", "")[:5000] if result.get("output") else None,
        error=result.get("error", "")[:2000] if result.get("error") else None,
        execution_time_ms=result.get("execution_time_ms", 0),
        status=result.get("status", "error"),
    )
    db.add(log_entry)
    db.commit()

    return CodeExecutionWithTestsResponse(
        output=result.get("output"),
        error=result.get("error"),
        status=result.get("status", "error"),
        execution_time_ms=result.get("execution_time_ms", 0),
        test_results=test_results,
    )


def execute_snippet(
    db: Session,
    user_id: int,
    snippet: CodeSnippetORM,
    input_data: Optional[str] = None,
    run_tests: bool = True,
) -> CodeExecutionWithTestsResponse:
    """Execute a saved code snippet with optional test cases"""
    
    # Execute the main code
    result = CodeExecutor.execute(
        code=snippet.code,
        language=snippet.language,
        input_data=input_data,
        timeout=snippet.execution_timeout,
    )
    
    test_results = None
    if run_tests and snippet.test_cases:
        test_results = run_test_cases_against_code(
            snippet.code,
            snippet.language,
            snippet.execution_timeout,
            snippet.test_cases,
        )
    
    # Log the execution
    log_entry = CodeExecutionLogORM(
        code_snippet_id=snippet.id,
        authuser_id=user_id,
        language=snippet.language,
        code_executed=snippet.code[:5000],
        input_data=input_data[:1000] if input_data else None,
        output=result.get("output", "")[:5000] if result.get("output") else None,
        error=result.get("error", "")[:2000] if result.get("error") else None,
        execution_time_ms=result.get("execution_time_ms", 0),
        status=result.get("status", "error"),
    )
    db.add(log_entry)
    
    # Update snippet's last_executed_at
    snippet.last_executed_at = datetime.now()
    db.commit()
    db.refresh(snippet)
    
    return CodeExecutionWithTestsResponse(
        output=result.get("output"),
        error=result.get("error"),
        status=result.get("status", "error"),
        execution_time_ms=result.get("execution_time_ms", 0),
        test_results=test_results,
    )


def get_execution_logs(
    db: Session,
    user_id: int,
    snippet_id: Optional[int] = None,
    limit: int = 50,
) -> List[CodeExecutionLogORM]:
    """Get execution logs for a user"""
    query = db.query(CodeExecutionLogORM).filter(
        CodeExecutionLogORM.authuser_id == user_id
    )
    
    if snippet_id:
        query = query.filter(CodeExecutionLogORM.code_snippet_id == snippet_id)
    
    return query.order_by(CodeExecutionLogORM.created_at.desc()).limit(limit).all()


# ==================== Code Sharing ====================

def share_snippet(
    db: Session,
    snippet: CodeSnippetORM,
    user_ids: List[int],
) -> None:
    """Share a code snippet with other users (read-only)"""
    # Get current shared_with list
    shared_with = snippet.shared_with or []
    if isinstance(shared_with, str):
        shared_with = json.loads(shared_with)
    
    # Add new users avoiding duplicates
    for user_id in user_ids:
        if user_id not in shared_with:
            shared_with.append(user_id)
    
    snippet.shared_with = shared_with
    snippet.is_shared = True
    db.commit()
    
    logger.info(f"Shared snippet {snippet.id} with users {user_ids}")


def unshare_snippet(
    db: Session,
    snippet: CodeSnippetORM,
    user_ids: List[int],
) -> None:
    """Remove sharing of a code snippet"""
    # Get current shared_with list
    shared_with = snippet.shared_with or []
    if isinstance(shared_with, str):
        shared_with = json.loads(shared_with)
    
    # Remove users
    shared_with = [uid for uid in shared_with if uid not in user_ids]
    
    snippet.shared_with = shared_with if shared_with else None
    snippet.is_shared = len(shared_with) > 0
    db.commit()
    
    logger.info(f"Unshared snippet {snippet.id} with users {user_ids}")


def get_shared_snippets(db: Session, user_id: int) -> List[CodeSnippetORM]:
    """Get code snippets shared with a user (read-only access)"""
    # Query snippets where user_id is in the shared_with list
    # This requires checking if user_id is in the JSON array
    snippets = db.query(CodeSnippetORM).filter(
        CodeSnippetORM.shared_with.isnot(None),
        CodeSnippetORM.is_shared == True,
    ).all()
    
    # Filter in Python (since JSON query varies by DB)
    result = []
    for snippet in snippets:
        shared_with = snippet.shared_with
        if isinstance(shared_with, str):
            shared_with = json.loads(shared_with)
        if shared_with and user_id in shared_with:
            result.append(snippet)
    
    return sorted(result, key=lambda x: x.updated_at, reverse=True)


# ==================== Admin questions (assignments) ====================

def list_questions(
    db: Session,
    include_inactive: bool = False,
    is_staff: bool = False,
    current_user_id: Optional[int] = None,
) -> List[CoderpadQuestionORM]:
    q = db.query(CoderpadQuestionORM)
    if not include_inactive:
        q = q.filter(CoderpadQuestionORM.is_active == True)
    rows = q.order_by(
        CoderpadQuestionORM.sno.asc(),
        CoderpadQuestionORM.sort_order.asc(),
        CoderpadQuestionORM.id.asc(),
    ).all()

    if is_staff or current_user_id is None:
        return rows

    # Candidate view: only include assignments explicitly assigned to them,
    # plus global assignments where assigned_candidate_ids is empty/null.
    filtered: List[CoderpadQuestionORM] = []
    for row in rows:
        assigned = row.assigned_candidate_ids
        if not assigned:
            filtered.append(row)
            continue
        if isinstance(assigned, str):
            try:
                assigned = json.loads(assigned)
            except Exception:
                assigned = []
        if isinstance(assigned, list) and current_user_id in assigned:
            filtered.append(row)
    return filtered


def get_question_by_id(db: Session, question_id: int) -> Optional[CoderpadQuestionORM]:
    return db.query(CoderpadQuestionORM).filter(CoderpadQuestionORM.id == question_id).first()


def create_question(
    db: Session,
    admin_user_id: int,
    data: CoderpadQuestionCreate,
) -> CoderpadQuestionORM:
    # Allow blank problem text when title is set (new question shell from UI).
    q_in = data.question
    p_in = data.problem_statement
    if q_in is not None:
        question_text = (q_in or "").strip()
    elif p_in is not None:
        question_text = (p_in or "").strip()
    else:
        question_text = ""

    if p_in is not None:
        problem_statement_text = (p_in or "").strip()
    else:
        problem_statement_text = question_text

    title_text = (data.title or "").strip()
    if not title_text and not question_text and not problem_statement_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="title or problem text is required",
        )
    if not title_text:
        combined = (question_text or problem_statement_text).strip()
        title_text = (combined[:80] if combined else "CoderPad question")

    tc = None
    if data.test_cases:
        tc = [tc.model_dump() for tc in data.test_cases]
    assigned_ids = data.assigned_candidate_ids or None
    row = CoderpadQuestionORM(
        sno=data.sno if data.sno is not None else data.sort_order,
        question=question_text,
        title=title_text,
        problem_statement=problem_statement_text,
        test_case_1=data.test_case_1,
        test_case_2=data.test_case_2,
        test_case_3=data.test_case_3,
        test_case_4=data.test_case_4,
        test_case_5=data.test_case_5,
        test_case_6=data.test_case_6,
        test_case_7=data.test_case_7,
        test_case_8=data.test_case_8,
        test_case_9=data.test_case_9,
        test_case_10=data.test_case_10,
        language=data.language,
        starter_code=data.starter_code,
        test_cases=tc,
        assigned_candidate_ids=assigned_ids,
        execution_timeout=data.execution_timeout,
        is_active=data.is_active,
        sort_order=data.sort_order,
        created_by_user_id=admin_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("Created coderpad question %s", row.id)
    return row


def update_question(
    db: Session,
    row: CoderpadQuestionORM,
    data: CoderpadQuestionUpdate,
) -> CoderpadQuestionORM:
    payload = data.model_dump(exclude_unset=True)
    if "test_cases" in payload and data.test_cases is not None:
        payload["test_cases"] = [tc.model_dump() for tc in data.test_cases]
    if "assigned_candidate_ids" in payload and payload["assigned_candidate_ids"] == []:
        payload["assigned_candidate_ids"] = None
    if "question" in payload and payload["question"] is not None:
        payload["question"] = payload["question"].strip()
    if "problem_statement" in payload and payload["problem_statement"] is not None:
        payload["problem_statement"] = payload["problem_statement"].strip()

    # UI sends `problem_statement`; keep DB `question` in sync (both Text, same content).
    if "problem_statement" in payload:
        ps = payload["problem_statement"]
        payload["question"] = ps
    elif "question" in payload:
        payload["problem_statement"] = payload["question"]

    merged_q = payload.get("question", row.question)
    merged_p = payload.get("problem_statement", row.problem_statement)
    normalized_question = (merged_q or merged_p or "").strip()
    next_title = (payload.get("title", row.title) or "").strip()
    if not normalized_question and not next_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question or title is required",
        )

    payload["question"] = normalized_question
    payload["problem_statement"] = normalized_question
    if "sno" in payload and "sort_order" not in payload:
        payload["sort_order"] = payload["sno"]

    for k, v in payload.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def delete_question(db: Session, row: CoderpadQuestionORM) -> None:
    db.delete(row)
    db.commit()


def list_assignable_candidates(
    db: Session,
    search: Optional[str] = None,
    limit: int = 100,
    resolve_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Return auth users linked to candidate rows (email matches auth uname).
    Optional search filters by candidate full name or email (ILIKE).
    Optional resolve_ids returns those auth users (for showing selected labels).
    """
    limit = max(1, min(limit, 200))
    search = _sanitize_search_term(search)

    if resolve_ids is not None and len(resolve_ids) > 0:
        uids = [i for i in resolve_ids if isinstance(i, int) and i > 0][:limit]
        if not uids:
            return []
        users = (
            db.query(AuthUserORM)
            .filter(AuthUserORM.id.in_(uids))
            .filter(AuthUserORM.uname.isnot(None))
            .all()
        )
        emails_lower = {(u.uname or "").strip().lower() for u in users if u.uname}
        if not emails_lower:
            return []
        cands = (
            db.query(CandidateORM)
            .filter(sa_func.lower(sa_func.trim(CandidateORM.email)).in_(list(emails_lower)))
            .all()
        )
        by_email = {(c.email or "").strip().lower(): c for c in cands if c.email}
        out: List[Dict[str, Any]] = []
        for u in users:
            em = (u.uname or "").strip().lower()
            c = by_email.get(em)
            if not c:
                continue
            disp = (c.full_name or u.fullname or u.uname or "").strip() or u.uname
            out.append(
                {
                    "id": u.id,
                    "username": (u.uname or "").strip(),
                    "display_name": disp,
                }
            )
        out.sort(key=lambda x: (x["display_name"].lower(), x["username"].lower()))
        return out

    cand_q = (
        db.query(CandidateORM)
        .filter(CandidateORM.email.isnot(None))
        .filter(sa_func.trim(CandidateORM.email) != "")
    )
    if search:
        # Bound parameter via SQLAlchemy; % wildcards are part of the value, not SQL text.
        term = f"%{search}%"
        cand_q = cand_q.filter(
            or_(
                CandidateORM.full_name.ilike(term),
                CandidateORM.email.ilike(term),
            )
        )

    candidates = cand_q.order_by(CandidateORM.full_name.asc()).all()
    emails_lower = {
        (c.email or "").strip().lower()
        for c in candidates
        if c.email and (c.email or "").strip()
    }
    if not emails_lower:
        return []

    users = (
        db.query(AuthUserORM)
        .filter(sa_func.lower(sa_func.trim(AuthUserORM.uname)).in_(list(emails_lower)))
        .all()
    )
    by_uname = {(u.uname or "").strip().lower(): u for u in users if u.uname}

    out = []
    seen_uids = set()
    for c in candidates:
        em = (c.email or "").strip().lower()
        u = by_uname.get(em)
        if not u or u.id in seen_uids:
            continue
        seen_uids.add(u.id)
        disp = (c.full_name or u.fullname or u.uname or "").strip() or u.uname
        out.append(
            {
                "id": u.id,
                "username": (u.uname or "").strip(),
                "display_name": disp,
            }
        )
    out.sort(key=lambda x: (x["display_name"].lower(), x["username"].lower()))
    return out[:limit]

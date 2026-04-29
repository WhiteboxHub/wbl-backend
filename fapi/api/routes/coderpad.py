from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.models import AuthUserORM, CodeSnippetORM, CodeExecutionLogORM
from fapi.db.schemas import (
    CodeSnippetCreate,
    CodeSnippetUpdate,
    CodeSnippetOut,
    CodeSnippetListOut,
    CodeExecutionRequest,
    CodeExecutionWithTestsResponse,
    CodeExecutionLogOut,
    CoderpadQuestionCreate,
    CoderpadQuestionUpdate,
    CoderpadQuestionOut,
    CoderpadAssignableCandidateOut,
    CoderpadLlmValidateRequest,
    CoderpadLlmValidateResponse,
)
from fapi.utils.auth_dependencies import get_current_user, staff_or_admin_required
from fapi.utils import coderpad_utils
from fapi.utils.coderpad_llm_utils import llm_validate_code_submission
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coderpad", tags=["CoderPad"])

# Aligns with coderpad_utils list_assignable_candidates limits (ORM-bound params only).
_MAX_ASSIGNABLE_SEARCH = 200
_MAX_RESOLVE_IDS = 200


def _resolve_openai_api_key(header_key: Optional[str]) -> str:
    """Prefer per-request header; else CODERPAD_OPENAI_API_KEY, then OPENAI_API_KEY (e.g. from .env)."""
    k = (header_key or "").strip()
    if k:
        return k
    return (os.getenv("CODERPAD_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


# ==================== Code Snippet CRUD ====================

@router.get("/snippets", response_model=List[CodeSnippetListOut])
def get_user_snippets(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all code snippets for current user"""
    return coderpad_utils.get_user_snippets(db, current_user.id)


@router.get("/snippets/{snippet_id}", response_model=CodeSnippetOut)
def get_snippet(
    snippet_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific code snippet by ID"""
    snippet = coderpad_utils.get_snippet_by_id(db, snippet_id, current_user.id)
    if not snippet:
        raise HTTPException(
            status_code=404,
            detail="Code snippet not found or access denied"
        )
    return snippet


@router.post("/snippets", response_model=CodeSnippetOut, status_code=status.HTTP_201_CREATED)
def create_snippet(
    snippet_data: CodeSnippetCreate,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new code snippet"""
    return coderpad_utils.create_snippet(db, current_user.id, snippet_data)


@router.put("/snippets/{snippet_id}", response_model=CodeSnippetOut)
def update_snippet(
    snippet_id: int,
    snippet_data: CodeSnippetUpdate,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a code snippet"""
    snippet = coderpad_utils.get_snippet_by_id(db, snippet_id, current_user.id)
    if not snippet:
        raise HTTPException(
            status_code=404,
            detail="Code snippet not found or access denied"
        )
    return coderpad_utils.update_snippet(db, snippet, snippet_data)


@router.delete("/snippets/{snippet_id}")
def delete_snippet(
    snippet_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a code snippet"""
    snippet = coderpad_utils.get_snippet_by_id(db, snippet_id, current_user.id)
    if not snippet:
        raise HTTPException(
            status_code=404,
            detail="Code snippet not found or access denied"
        )
    coderpad_utils.delete_snippet(db, snippet)
    return {"message": "Code snippet deleted successfully"}


# ==================== Code Execution ====================

@router.post("/execute", response_model=CodeExecutionWithTestsResponse)
def execute_code(
    request: CodeExecutionRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute code directly without saving. Optional test_cases runs stdin tests (assignments)."""
    return coderpad_utils.execute_code_direct(db, current_user.id, request)


@router.post("/llm-validate", response_model=CoderpadLlmValidateResponse)
def llm_validate_coderpad(
    body: CoderpadLlmValidateRequest,
    x_openai_api_key: Optional[str] = Header(None, alias="X-OpenAI-Api-Key"),
    current_user: AuthUserORM = Depends(get_current_user),
):
    """
    Validate candidate code against the problem + test cases using OpenAI.
    Key resolution: optional X-OpenAI-Api-Key header, else server env
    CODERPAD_OPENAI_API_KEY or OPENAI_API_KEY (not persisted in DB yet).
    """
    key = _resolve_openai_api_key(x_openai_api_key)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key not configured: set CODERPAD_OPENAI_API_KEY or OPENAI_API_KEY on the server, or send X-OpenAI-Api-Key",
        )
    if not (body.problem_statement or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="problem_statement is required",
        )
    model = (body.model or "gpt-4o-mini").strip()
    result = llm_validate_code_submission(
        problem_statement=body.problem_statement.strip(),
        code=body.code,
        language=body.language or "python",
        test_cases=body.test_cases,
        openai_api_key=key,
        model=model,
    )
    return CoderpadLlmValidateResponse(**result)


@router.post("/snippets/{snippet_id}/execute", response_model=CodeExecutionWithTestsResponse)
def execute_snippet(
    snippet_id: int,
    input_data: Optional[str] = None,
    run_tests: Optional[bool] = True,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute a saved code snippet with optional test cases"""
    snippet = coderpad_utils.get_snippet_by_id(db, snippet_id, current_user.id)
    if not snippet:
        raise HTTPException(
            status_code=404,
            detail="Code snippet not found or access denied"
        )
    return coderpad_utils.execute_snippet(db, current_user.id, snippet, input_data, run_tests)


@router.get("/execution-logs", response_model=List[CodeExecutionLogOut])
def get_execution_logs(
    snippet_id: Optional[int] = None,
    limit: int = 50,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get execution logs for current user"""
    return coderpad_utils.get_execution_logs(db, current_user.id, snippet_id, limit)


# ==================== Code Sharing ====================

@router.post("/snippets/{snippet_id}/share")
def share_snippet(
    snippet_id: int,
    user_ids: List[int],
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Share a code snippet with other users (read-only)"""
    snippet = coderpad_utils.get_snippet_by_id(db, snippet_id, current_user.id)
    if not snippet:
        raise HTTPException(
            status_code=404,
            detail="Code snippet not found or access denied"
        )
    coderpad_utils.share_snippet(db, snippet, user_ids)
    return {"message": "Code snippet shared successfully"}


@router.post("/snippets/{snippet_id}/unshare")
def unshare_snippet(
    snippet_id: int,
    user_ids: List[int],
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove sharing of a code snippet"""
    snippet = coderpad_utils.get_snippet_by_id(db, snippet_id, current_user.id)
    if not snippet:
        raise HTTPException(
            status_code=404,
            detail="Code snippet not found or access denied"
        )
    coderpad_utils.unshare_snippet(db, snippet, user_ids)
    return {"message": "Code snippet sharing removed successfully"}


@router.get("/shared-with-me", response_model=List[CodeSnippetListOut])
def get_shared_snippets(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get code snippets shared by other users with current user"""
    return coderpad_utils.get_shared_snippets(db, current_user.id)


# ==================== Assignments (admin-authored questions) ====================

@router.get("/questions", response_model=List[CoderpadQuestionOut])
def list_coderpad_questions(
    include_inactive: bool = False,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List assignment questions. Learners see active only; staff may pass include_inactive=true."""
    is_staff = (
        getattr(current_user, "role", None) == "admin"
        or getattr(current_user, "is_admin", False)
        or getattr(current_user, "is_employee", False)
        or (getattr(current_user, "uname", "") or "").lower() == "admin"
    )
    if include_inactive and not is_staff:
        raise HTTPException(status_code=403, detail="Staff privileges required")
    return coderpad_utils.list_questions(
        db,
        include_inactive=include_inactive and is_staff,
        is_staff=is_staff,
        current_user_id=current_user.id,
    )


@router.get("/assignable-candidates", response_model=List[CoderpadAssignableCandidateOut])
def list_assignable_candidates(
    search: Optional[str] = Query(
        None,
        max_length=_MAX_ASSIGNABLE_SEARCH,
        description="Filter by candidate name or email (bounded length; passed as ORM bind param).",
    ),
    limit: int = Query(100, ge=1, le=200),
    resolve_ids: Optional[str] = Query(
        None,
        max_length=4000,
        description="Comma-separated auth user ids to resolve names (numeric ids only; max 200).",
    ),
    current_user: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    id_list: Optional[List[int]] = None
    if resolve_ids and resolve_ids.strip():
        id_list = []
        for part in resolve_ids.split(","):
            if len(id_list) >= _MAX_RESOLVE_IDS:
                break
            p = part.strip()
            if p.isdigit():
                id_list.append(int(p))
        if not id_list:
            id_list = None
    return coderpad_utils.list_assignable_candidates(
        db, search=search, limit=limit, resolve_ids=id_list
    )


@router.get("/questions/{question_id}", response_model=CoderpadQuestionOut)
def get_coderpad_question(
    question_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = coderpad_utils.get_question_by_id(db, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    is_staff = (
        getattr(current_user, "role", None) == "admin"
        or getattr(current_user, "is_admin", False)
        or getattr(current_user, "is_employee", False)
        or (getattr(current_user, "uname", "") or "").lower() == "admin"
    )
    if not row.is_active and not is_staff:
        raise HTTPException(status_code=404, detail="Question not found")
    return row


@router.post("/questions", response_model=CoderpadQuestionOut, status_code=status.HTTP_201_CREATED)
def create_coderpad_question(
    body: CoderpadQuestionCreate,
    current_user: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Admin: publish a new coding assignment."""
    return coderpad_utils.create_question(db, current_user.id, body)


@router.put("/questions/{question_id}", response_model=CoderpadQuestionOut)
def update_coderpad_question(
    question_id: int,
    body: CoderpadQuestionUpdate,
    current_user: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    row = coderpad_utils.get_question_by_id(db, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    return coderpad_utils.update_question(db, row, body)


@router.delete("/questions/{question_id}")
def delete_coderpad_question(
    question_id: int,
    current_user: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    row = coderpad_utils.get_question_by_id(db, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    coderpad_utils.delete_question(db, row)
    return {"message": "Question deleted"}

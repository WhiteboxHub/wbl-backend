from fastapi import APIRouter, Depends, Header, HTTPException, status, Query, Response
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
    CoderpadTrackingLogsResponse,
    CoderpadQuestionCreate,
    CoderpadQuestionUpdate,
    CoderpadQuestionOut,
    CoderpadAssignableCandidateOut,
    CoderpadLlmValidateRequest,
    CoderpadLlmValidateResponse,
    CoderpadLlmGenerateRequest,
    CoderpadLlmGenerateResponse,
    CoderpadMyOpenaiKeyStatusOut,
    CoderpadMyOpenaiKeyPreviewOut,
    CoderpadMyOpenaiKeyRevealOut,
    CoderpadSaveOpenaiKeyRequest,
    CoderpadSaveLlmKeyRequest,
    CoderpadUpdateLlmKeyRequest,
    CandidateLlmKeyListItemOut,
    CoderpadLlmKeyValidateBatchIn,
    CoderpadLlmKeyValidateBatchOut,
    CoderpadLlmKeyValidateResultOut,
    CoderpadLlmKeyVoiceEnabledIn,
    CoderpadLlmKeyIsDefaultIn,
)
from fapi.utils.auth_dependencies import get_current_user, staff_or_admin_required
from fapi.utils import coderpad_utils
from fapi.utils.coderpad_llm_utils import llm_validate_code_submission, llm_generate_question_from_topic
from fapi.utils.coderpad_openai_key import (
    CODERPAD_MISSING_OPENAI_KEY_MSG,
    candidate_has_openai_key_in_db,
    get_stored_openai_key_for_owner,
    openai_key_configured_for_user,
    openai_key_db_preview_for_user,
    resolve_coderpad_openai_api_key,
    save_candidate_openai_key_to_db,
    create_candidate_llm_key_to_db,
    update_candidate_llm_key_to_db,
    list_candidate_llm_keys_for_user,
    reveal_candidate_llm_key_by_id,
    delete_candidate_llm_key_for_user,
    update_candidate_llm_key_voice_enabled,
    update_candidate_llm_key_is_default,
    validate_llm_key_batch_for_user,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coderpad", tags=["CoderPad"])

# Aligns with coderpad_utils list_assignable_candidates limits (ORM-bound params only).
_MAX_ASSIGNABLE_SEARCH = 200
_MAX_RESOLVE_IDS = 200


# -------------------- Candidate OpenAI key (DB) --------------------


@router.get("/me/openai-key-status", response_model=CoderpadMyOpenaiKeyStatusOut)
def get_my_openai_key_status(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """True if LLM can run without pasting a key (stored row or server env)."""
    return CoderpadMyOpenaiKeyStatusOut(
        configured=openai_key_configured_for_user(db, current_user),
        stored_in_db=candidate_has_openai_key_in_db(db, current_user),
    )


@router.get("/me/openai-key-preview", response_model=CoderpadMyOpenaiKeyPreviewOut)
def get_my_openai_key_preview(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Masked hint for the OpenAI key stored for ``candidate.id`` (full key never returned)."""
    has_stored, masked, key_id = openai_key_db_preview_for_user(db, current_user)
    return CoderpadMyOpenaiKeyPreviewOut(
        has_stored_key=has_stored,
        masked_preview=masked,
        key_id=key_id,
    )


@router.get("/me/openai-key-reveal", response_model=CoderpadMyOpenaiKeyRevealOut)
def reveal_my_openai_key(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the full stored OpenAI key for the authenticated candidate (explicit reveal only)."""
    raw = get_stored_openai_key_for_owner(db, current_user)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No OpenAI API key stored for your account.",
        )
    return CoderpadMyOpenaiKeyRevealOut(api_key=raw)


@router.post("/me/openai-api-key", status_code=status.HTTP_204_NO_CONTENT)
def save_my_openai_api_key(
    body: CoderpadSaveOpenaiKeyRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store or replace the candidate's OpenAI key in ``candidate_llm_api_keys``."""
    try:
        save_candidate_openai_key_to_db(
            db,
            current_user,
            body.api_key,
            body.model_name,
            body.voice_enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/llm-keys", status_code=status.HTTP_204_NO_CONTENT)
def create_my_llm_key(
    body: CoderpadSaveLlmKeyRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store a new LLM API key for a supported provider."""
    try:
        create_candidate_llm_key_to_db(
            db,
            current_user,
            body.provider_name,
            body.api_key,
            body.model_name,
            body.voice_enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/me/llm-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_my_llm_key(
    key_id: int,
    body: CoderpadUpdateLlmKeyRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update provider, model, speech flag, and optionally replace the API key."""
    try:
        update_candidate_llm_key_to_db(
            db,
            current_user,
            key_id,
            body.provider_name,
            body.api_key,
            body.model_name,
            body.voice_enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/llm-keys", response_model=List[CandidateLlmKeyListItemOut])
def list_my_llm_keys(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List masked LLM keys from ``candidate_llm_api_keys`` for ``candidate.id`` linked to this user."""
    try:
        rows = list_candidate_llm_keys_for_user(db, current_user)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("list_my_llm_keys failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    return [CandidateLlmKeyListItemOut(**r) for r in rows]


@router.get("/me/llm-keys/{key_id}/reveal", response_model=CoderpadMyOpenaiKeyRevealOut)
def reveal_my_llm_key(
    key_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return full stored key for one row (owner only)."""
    try:
        raw = reveal_candidate_llm_key_by_id(db, current_user, key_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return CoderpadMyOpenaiKeyRevealOut(api_key=raw)


@router.patch("/me/llm-keys/{key_id}/voice-enabled", status_code=status.HTTP_204_NO_CONTENT)
def patch_my_llm_key_voice_enabled(
    key_id: int,
    body: CoderpadLlmKeyVoiceEnabledIn,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update speech-enabled flag for one LLM key row."""
    try:
        update_candidate_llm_key_voice_enabled(
            db, current_user, key_id, body.voice_enabled
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/me/llm-keys/{key_id}/is-default", status_code=status.HTTP_204_NO_CONTENT)
def patch_my_llm_key_is_default(
    key_id: int,
    body: CoderpadLlmKeyIsDefaultIn,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or clear the default LLM key for this candidate."""
    try:
        update_candidate_llm_key_is_default(
            db, current_user, key_id, body.is_default
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/llm-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_llm_key(
    key_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete one row from ``candidate_llm_api_keys``."""
    try:
        delete_candidate_llm_key_for_user(db, current_user, key_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/llm-keys/validate-batch", response_model=CoderpadLlmKeyValidateBatchOut)
def validate_my_llm_keys_batch(
    body: CoderpadLlmKeyValidateBatchIn,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate stored keys (active / inactive / invalid) via provider APIs."""
    try:
        raw = validate_llm_key_batch_for_user(
            db,
            current_user,
            [k.model_dump() for k in body.keys],
            body.session_id,
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return CoderpadLlmKeyValidateBatchOut(
        results=[CoderpadLlmKeyValidateResultOut(**r) for r in raw]
    )


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
    db: Session = Depends(get_db),
):
    """
    Validate candidate code against the problem + test cases using OpenAI.
    Uses ``X-OpenAI-Api-Key`` when provided; otherwise the candidate's **default**
  My LLM key when OpenAI, else latest OpenAI row, then server env keys.
    """
    key = resolve_coderpad_openai_api_key(db, current_user, x_openai_api_key)

    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CODERPAD_MISSING_OPENAI_KEY_MSG,
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


@router.post("/llm-generate", response_model=CoderpadLlmGenerateResponse)
def llm_generate_question(
    body: CoderpadLlmGenerateRequest,
    x_openai_api_key: Optional[str] = Header(None, alias="X-OpenAI-Api-Key"),
    current_user: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """
    Generate a CoderPad question (title, statement, starter code, test cases) from a topic.
    """
    key = resolve_coderpad_openai_api_key(db, current_user, x_openai_api_key)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CODERPAD_MISSING_OPENAI_KEY_MSG,
        )
    if not (body.topic or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="topic is required",
        )

    model = (body.model or "gpt-4o-mini").strip()
    result = llm_generate_question_from_topic(
        topic=body.topic.strip(),
        language=body.language or "python",
        openai_api_key=key,
        model=model,
    )

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"]
        )

    return CoderpadLlmGenerateResponse(**result)


@router.post("/questions/{question_id}/update-statement-with-llm", response_model=CoderpadLlmGenerateResponse)
def update_question_statement_with_llm(
    question_id: int,
    body: CoderpadLlmGenerateRequest,
    x_openai_api_key: Optional[str] = Header(None, alias="X-OpenAI-Api-Key"),
    current_user: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """
    Generate an updated problem statement for an existing CoderPad question using LLM.
    Takes the same topic/language/model as llm-generate, generates a new statement,
    and updates the question with the generated content.
    """
    # Verify question exists
    question_row = coderpad_utils.get_question_by_id(db, question_id)
    if not question_row:
        raise HTTPException(status_code=404, detail="Question not found")

    key = resolve_coderpad_openai_api_key(db, current_user, x_openai_api_key)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CODERPAD_MISSING_OPENAI_KEY_MSG,
        )
    if not (body.topic or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="topic is required",
        )

    model = (body.model or "gpt-4o-mini").strip()
    result = llm_generate_question_from_topic(
        topic=body.topic.strip(),
        language=body.language or "python",
        openai_api_key=key,
        model=model,
    )

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"]
        )

    # Update the question with the generated content
    update_data = CoderpadQuestionUpdate(
        problem_statement=result.get("problem_statement"),
        starter_code=result.get("starter_code"),
        test_cases=result.get("test_cases"),
        language=result.get("language", body.language or "python"),
    )
    coderpad_utils.update_question(db, question_row, update_data)

    return CoderpadLlmGenerateResponse(**result)


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


@router.get("/tracking/execution-logs", response_model=CoderpadTrackingLogsResponse)
def get_tracking_execution_logs(
    limit: int = Query(1000, ge=1, le=5000),
    current_user: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Staff: all CoderPad execution logs with candidate name/email for Avatar tracking."""
    logs = coderpad_utils.get_tracking_execution_logs(db, limit=limit)
    return {"data": logs}


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

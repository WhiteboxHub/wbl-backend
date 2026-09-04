# AIPrep API Endpoints Contract

**Base URL:** `/api/aiprep`

---

## Part 1: Assessment Execution Flow

### 1. Create Assessment
**Endpoint:** `POST /assessments`
**Description:** Initializes a new assessment session for a candidate. *(Note: `ip_address` and `user_agent` read from headers).*

**Request:**
```json
{
  "candidate_id": 1001,
  "assessment_type": "TECHNICAL",
  "media_type": "VIDEO",
  "job_description": null
}
```

**Response (201):**
```json
{
  "id": 12345,
  "status": "IN_PROGRESS",
  "started_at": "2026-09-02T10:00:00Z"
}
```

### 2. Submit Assessment Data
**Endpoint:** `POST /assessments/{id}/data`
**Description:** Submits captured telemetry and raw data from UI.

**Request:**
```json
{
  "questions": [ { "question_id": 101, "question_text": "Explain RAG." } ],
  "transcript": { "full_text": "RAG stands for...", "segments": [] },
  "audio_telemetry": { "words_per_minute": 135, "silence_ratio_pct": 12.5 },
  "video_telemetry": { "face_visible_pct": 98.5, "head_nods_count": 12 }
}
```

**Response (200):**
```json
{ "message": "Data saved successfully" }
```

### 3. Update Assessment Media URL
**Endpoint:** `PATCH /assessments/{id}/media`
**Description:** Updates the `youtube_url` after media processing.

**Request:**
```json
{ "youtube_url": "https://youtube.com/watch?v=..." }
```

**Response (200):**
```json
{ "id": 12345, "youtube_url": "https://youtube.com/watch?v=..." }
```

### 4. Trigger Evaluation
**Endpoint:** `POST /assessments/{id}/evaluate`
**Description:** Changes status to `EVALUATING` and triggers the Orchestrator.

**Request:** `{}`

**Response (202):**
```json
{ "id": 12345, "status": "EVALUATING" }
```

### 5. Get Assessment Report
**Endpoint:** `GET /assessments/{id}`
**Description:** Fetches complete assessment including data and report evaluation.

**Response (200):**
```json
{
  "id": 12345,
  "candidate_id": 1001,
  "assessment_type": "TECHNICAL",
  "media_type": "VIDEO",
  "status": "COMPLETED",
  "youtube_url": "https://youtube.com/watch?v=...",
  "data": { ... },
  "report": { ... }
}
```

---

## Part 2: Candidate Dashboard

### 6. List Candidate Assessments
**Endpoint:** `GET /assessments?candidate_id={id}`
**Description:** Fetches a list of all assessments for a candidate.

**Response (200):**
```json
{
  "items": [
    {
      "id": 12345,
      "assessment_type": "TECHNICAL",
      "media_type": "VIDEO",
      "status": "COMPLETED",
      "created_at": "2026-09-02T10:00:00Z"
    }
  ],
  "total": 1
}
```

---

## Part 3: Admin / Question Bank

### 7. List Questions
**Endpoint:** `GET /questions`
**Description:** Fetches questions for the admin grid or assessment engine. Supports query params like `?category=TECHNICAL&difficulty_level=MEDIUM`.

**Response (200):**
```json
{
  "items": [
    {
      "id": 101,
      "category": "TECHNICAL",
      "sub_category": "Agentic AI",
      "difficulty_level": "MEDIUM",
      "question_text": "Explain the ReAct pattern.",
      "is_active": true,
      "created_at": "2026-09-01T12:00:00Z"
    }
  ],
  "total": 1
}
```

### 8. Create Question
**Endpoint:** `POST /questions`
**Description:** Adds a new question to the database.

**Request:**
```json
{
  "category": "TECHNICAL",
  "sub_category": "Agentic AI",
  "difficulty_level": "HARD",
  "question_text": "Design a multi-agent orchestration framework.",
  "is_active": true
}
```

**Response (201):**
```json
{
  "id": 102,
  "category": "TECHNICAL",
  "sub_category": "Agentic AI",
  "difficulty_level": "HARD",
  "question_text": "Design a multi-agent orchestration framework.",
  "is_active": true,
  "created_at": "2026-09-02T15:00:00Z"
}
```

### 9. Update Question
**Endpoint:** `PATCH /questions/{id}`
**Description:** Updates fields on an existing question (e.g., soft-deleting by setting `is_active` to false).

**Request:**
```json
{
  "is_active": false
}
```

**Response (200):**
```json
{
  "id": 102,
  "category": "TECHNICAL",
  "sub_category": "Agentic AI",
  "difficulty_level": "HARD",
  "question_text": "Design a multi-agent orchestration framework.",
  "is_active": false,
  "created_at": "2026-09-02T15:00:00Z"
}
```

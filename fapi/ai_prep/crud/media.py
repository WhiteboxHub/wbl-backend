from typing import Optional
from sqlalchemy.orm import Session
from fapi.ai_prep.models import AiPrepMediaFileORM


def create_or_update_media_file(
    db: Session,
    assessment_id: int,
    audio_file_path: str,
    video_file_path: Optional[str] = None,
    duration_seconds: int = 0,
    file_size_bytes: int = 0
) -> AiPrepMediaFileORM:
    """Create or update media file record for an assessment."""
    media_file = db.query(AiPrepMediaFileORM).filter(
        AiPrepMediaFileORM.assessment_id == assessment_id
    ).first()

    if media_file:
        media_file.audio_file_path = audio_file_path
        if video_file_path is not None:
            media_file.video_file_path = video_file_path
        if duration_seconds > 0:
            media_file.duration_seconds = duration_seconds
        if file_size_bytes > 0:
            media_file.file_size_bytes = file_size_bytes
    else:
        media_file = AiPrepMediaFileORM(
            assessment_id=assessment_id,
            audio_file_path=audio_file_path,
            video_file_path=video_file_path,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size_bytes
        )
        db.add(media_file)

    db.commit()
    db.refresh(media_file)
    return media_file


def update_video_file_path(
    db: Session,
    assessment_id: int,
    video_file_path: str
) -> Optional[AiPrepMediaFileORM]:
    """Updates video file path to YouTube URL/ID after async upload."""
    media_file = db.query(AiPrepMediaFileORM).filter(
        AiPrepMediaFileORM.assessment_id == assessment_id
    ).first()
    if media_file:
        media_file.video_file_path = video_file_path
        db.commit()
        db.refresh(media_file)
    return media_file


def get_media_by_assessment_id(db: Session, assessment_id: int) -> Optional[AiPrepMediaFileORM]:
    """Retrieve media record by assessment_id."""
    return db.query(AiPrepMediaFileORM).filter(
        AiPrepMediaFileORM.assessment_id == assessment_id
    ).first()


def delete_media_by_assessment_id(db: Session, assessment_id: int) -> bool:
    """Delete media record for assessment_id."""
    media_file = get_media_by_assessment_id(db, assessment_id)
    if media_file:
        db.delete(media_file)
        db.commit()
        return True
    return False

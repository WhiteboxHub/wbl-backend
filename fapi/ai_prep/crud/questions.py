import random
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional
from fapi.ai_prep.models import AiPrepQuestionBank, AiPrepAssessmentQuestion, AiPrepAssessment, QuestionDifficultyEnum
from fapi.ai_prep.schemas import QuestionBankCreate

def get_questions(db: Session, category: str = None, difficulty: str = None, skip: int = 0, limit: int = 100):
    query = db.query(AiPrepQuestionBank).filter(AiPrepQuestionBank.is_active == True)
    if category:
        query = query.filter(AiPrepQuestionBank.category == category)
    if difficulty:
        query = query.filter(AiPrepQuestionBank.difficulty_level == difficulty)
    return query.offset(skip).limit(limit).all()

def create_question(db: Session, question: QuestionBankCreate):
    db_question = AiPrepQuestionBank(
        category=question.category,
        sub_category=question.sub_category,
        difficulty_level=question.difficulty_level,
        question_text=question.question_text,
        ideal_answer_rubric=question.ideal_answer_rubric,
        relevant_skills_json=question.relevant_skills_json,
        is_active=True
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

def get_random_questions_for_candidate(
    db: Session,
    candidate_id: int,
    category: str,
    difficulty: Optional[QuestionDifficultyEnum] = None,
    limit: int = 5
):
    # 1. Find all past assessments for this candidate
    past_assessments = db.query(AiPrepAssessment.id).filter(
        AiPrepAssessment.candidate_id == candidate_id
    ).all()
    past_assessment_ids = [a[0] for a in past_assessments]

    # 2. Find all question IDs they have already answered
    past_question_ids = []
    if past_assessment_ids:
        past_questions = db.query(AiPrepAssessmentQuestion.question_id).filter(
            AiPrepAssessmentQuestion.assessment_id.in_(past_assessment_ids)
        ).all()
        past_question_ids = [q[0] for q in past_questions]

    # 3. Query active questions in the requested category, excluding past questions
    query = db.query(AiPrepQuestionBank).filter(
        AiPrepQuestionBank.is_active == True,
        AiPrepQuestionBank.category == category
    )
    if past_question_ids:
        query = query.filter(AiPrepQuestionBank.id.notin_(past_question_ids))

    if difficulty:
        # Try to get questions of this specific difficulty first
        diff_query = query.filter(AiPrepQuestionBank.difficulty_level == difficulty)
        available_questions = diff_query.all()
        
        # If we have enough, randomize and return
        if len(available_questions) >= limit:
            return random.sample(available_questions, limit)
        
        # Otherwise, take all of this difficulty and fill remaining with other difficulties in the same category
        filled_questions = list(available_questions)
        remaining_limit = limit - len(filled_questions)
        
        other_query = query.filter(AiPrepQuestionBank.difficulty_level != difficulty)
        other_available = other_query.all()
        
        if len(other_available) <= remaining_limit:
            filled_questions.extend(other_available)
        else:
            filled_questions.extend(random.sample(other_available, remaining_limit))
            
        return filled_questions
    else:
        available_questions = query.all()
        if len(available_questions) <= limit:
            return available_questions
        return random.sample(available_questions, limit)

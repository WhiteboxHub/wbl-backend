import os
import sys
from sqlalchemy.orm import Session

# Add the wbl-backend root to python path to import fapi
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fapi.db.database import SessionLocal
from fapi.ai_prep.schemas import QuestionCreate, CategoryEnum, DifficultyEnum
from fapi.ai_prep.crud.questions import create_question

# Base questions to build from
BASE_QUESTIONS = {
    CategoryEnum.TECHNICAL: [
        ("Explain the difference between Fine-Tuning and RAG. When to use which?", "llm_knowledge"),
        ("How do you evaluate an LLM application?", "evaluation_methodology"),
        ("Explain attention mechanisms in transformers.", "core_engineering"),
        ("What are the trade-offs of quantizing a model?", "deployment_mlops"),
        ("How do you mitigate prompt injection attacks?", "llm_knowledge"),
        ("Explain how LoRA works for parameter efficient fine-tuning.", "llm_knowledge"),
        ("What is the difference between an encoder-only and decoder-only model?", "core_engineering"),
        ("Describe the process of setting up an evaluation pipeline using LLM-as-a-judge.", "evaluation_methodology"),
        ("How do you handle context window limits in large-scale document retrieval?", "rag_understanding")
    ],
    CategoryEnum.SYSTEM_DESIGN: [
        ("Design a scalable RAG system for 10 million PDFs.", "system_design"),
        ("Design a real-time recommendation engine using embeddings.", "system_design"),
        ("How would you architect a low-latency LLM serving infrastructure?", "deployment_mlops"),
        ("Design a multi-tenant vector database architecture.", "system_design"),
        ("Architect a data pipeline for continuous model pre-training.", "deployment_mlops"),
        ("Design a system to prevent PII leakage in LLM queries.", "system_design"),
        ("How do you scale model inference across multiple GPUs (e.g., pipeline vs tensor parallelism)?", "deployment_mlops"),
        ("Design a highly available prompt-caching layer.", "system_design"),
        ("Architect a microservice for document ingestion and embedding generation.", "system_design")
    ],
    CategoryEnum.BEHAVIORAL: [
        ("Tell me about a time you failed to meet a deadline.", "communication_clarity"),
        ("How do you resolve technical disagreements with senior engineers?", "stakeholder_thinking"),
        ("Describe a time you had to learn a new technology quickly.", "answer_structure"),
        ("Tell me about a complex project you led from start to finish.", "confidence"),
        ("How do you handle ambiguous project requirements?", "problem_framing"),
        ("Tell me about a time you mentored a junior team member.", "communication_clarity"),
        ("Describe a situation where you had to pivot your technical strategy midway.", "stakeholder_thinking"),
        ("How do you prioritize tech debt vs new features?", "problem_framing"),
        ("Tell me about a time you received difficult feedback.", "confidence")
    ],
    CategoryEnum.RECRUITER: [
        ("What are your salary expectations?", "confidence"),
        ("Why are you looking to leave your current role?", "communication_clarity"),
        ("What is your timeline for making a decision?", "answer_structure"),
        ("What are the top three things you look for in your next role?", "problem_framing"),
        ("How do you feel about working in a hybrid vs remote environment?", "communication_clarity"),
        ("Are you interviewing with any other companies currently?", "confidence"),
        ("What is your ideal company culture?", "stakeholder_thinking"),
        ("Where do you see your career in 5 years?", "problem_framing"),
        ("What was your favorite project in your last role?", "communication_clarity")
    ],
    CategoryEnum.HIRING_MANAGER: [
        ("Why do you want to join our specific engineering team?", "stakeholder_thinking"),
        ("What impact do you hope to make in your first 90 days?", "problem_framing"),
        ("How do you align your technical work with business goals?", "stakeholder_thinking"),
        ("What is your approach to cross-functional collaboration?", "communication_clarity"),
        ("Describe your ideal relationship with a product manager.", "stakeholder_thinking"),
        ("How do you ensure high code quality within your team?", "problem_framing"),
        ("What is a technology trend you are currently excited about?", "communication_clarity"),
        ("How do you balance speed of delivery with long-term maintainability?", "problem_framing"),
        ("Tell me about a time you drove a major architectural decision.", "confidence")
    ],
    CategoryEnum.GENERAL: [
        ("Please introduce yourself and your background.", "communication_clarity"),
        ("Walk me through your resume.", "answer_structure"),
        ("Why are you interested in this specific role?", "stakeholder_thinking"),
        ("What is your greatest professional strength?", "confidence"),
        ("What is a weakness you are actively working to improve?", "problem_framing"),
        ("Tell me about a project you are particularly proud of.", "communication_clarity"),
        ("How did you get into software engineering?", "answer_structure"),
        ("What do you consider your biggest career achievement?", "confidence"),
        ("What motivates you to do your best work?", "stakeholder_thinking")
    ]
}

difficulties = [DifficultyEnum.EASY, DifficultyEnum.MEDIUM, DifficultyEnum.HARD, DifficultyEnum.EXPERT]

def generate_seed_questions():
    seed_data = []
    # Generate 54 unique questions (9 per category)
    for category, questions in BASE_QUESTIONS.items():
        for idx, (q_text, skill) in enumerate(questions):
            # Rotate through difficulty levels to ensure all 4 are represented in the DB
            diff = difficulties[idx % 4] 
            
            q_data = {
                "category": category,
                "sub_category": f"Topic {idx+1}",
                "difficulty_level": diff,
                "question_text": q_text,
                "ideal_answer_rubric": f"Candidate should demonstrate proficiency in {skill} with clear reasoning.",
                "relevant_skills_json": {skill: 0.9, "communication_clarity": 0.5},
                "is_active": True
            }
            seed_data.append(q_data)
    
    return seed_data

def seed_database():
    questions = generate_seed_questions()
    print(f"Starting AI Prep Question Bank Seeding with {len(questions)} questions...")
    db: Session = SessionLocal()
    
    try:
        count = 0
        for q_data in questions:
            q_schema = QuestionCreate(**q_data)
            create_question(db, q_schema)
            count += 1
            
        print(f"Successfully seeded {count} questions into the database!")
    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()

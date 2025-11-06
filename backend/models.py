# models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from db import Base

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(1024), unique=True, index=True, nullable=False)
    title = Column(String(512), nullable=False)
    summary = Column(Text)
    key_entities = Column(JSON)        # {people:[], organizations:[], locations:[]}
    sections = Column(JSON)            # ["Early life", ...]
    related_topics = Column(JSON)      # ["Cryptography", ...]
    raw_html = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    prompt = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # ["A","B","C","D"]
    answer = Column(String(512), nullable=False)
    difficulty = Column(String(16))         # easy|medium|hard
    explanation = Column(Text)

    quiz = relationship("Quiz", back_populates="questions")

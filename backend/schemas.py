# schemas.py
from typing import List, Optional, Literal
from pydantic import BaseModel, HttpUrl, Field

Difficulty = Literal["easy", "medium", "hard"]

class QuestionOut(BaseModel):
    question: str = Field(alias="prompt")
    options: List[str]
    answer: str
    difficulty: Optional[Difficulty] = None
    explanation: Optional[str] = None
    class Config:
        populate_by_name = True

class QuizOut(BaseModel):
    id: int
    url: HttpUrl
    title: str
    summary: Optional[str]
    key_entities: dict
    sections: list
    quiz: List[QuestionOut]
    related_topics: List[str]

class GenerateIn(BaseModel):
    url: HttpUrl

class HistoryRow(BaseModel):
    id: int
    url: HttpUrl
    title: str
    created_at: str

class HistoryOut(BaseModel):
    items: list[HistoryRow]

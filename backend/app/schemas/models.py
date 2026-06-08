from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional

class ModuleType(str, Enum):
    WRITING = "writing"
    READING = "reading"

class PassageType(str, Enum):
    LONG = "long"
    SHORT = "short"

class PassageCategory(str, Enum):
    HUMANITIES = "humanities"
    SCIENCE = "science"
    SOCIAL_SCIENCE = "social_science"

class SkillType(str, Enum):
    VOCABULARY = "vocabulary"
    GRAMMAR = "grammar"
    COMPREHENSION = "comprehension"

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class DistractorRole(str, Enum):
    FACTUALLY_INCORRECT = "factually_incorrect"
    MISINTERPRETATION = "misinterpretation"
    IRRELEVANT = "irrelevant"

class TestStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

class QuestionFlag(str, Enum):
    AMBIGUOUS = "ambiguous"
    POORLY_PHRASED = "poorly_phrased"

class Passage(BaseModel):
    id: str
    text: str
    category: PassageCategory
    type: PassageType

class GeneratedQuestion(BaseModel):
    id: str
    question_text: str
    options: List[str]
    correct_option: int
    skill: SkillType
    difficulty: Difficulty

class GeneratedTest(BaseModel):
    id: str
    title: str

class GeneratedModule(BaseModel):
    id: str

class GeneratedPassageBlock(BaseModel):
    id: str

class TestBlueprint(BaseModel):
    id: str

class ModuleBlueprint(BaseModel):
    id: str

class PassageSlot(BaseModel):
    id: str

class DifficultyDistribution(BaseModel):
    easy: float
    medium: float
    hard: float

class QuestionFeedback(BaseModel):
    test_id: str
    question_id: str
    flag: QuestionFlag
    comment: str

class TestInventoryRecord(BaseModel):
    id: str

class GenerationJob(BaseModel):
    id: str
    status: TestStatus

class MistralQuestionOutput(BaseModel):
    question_text: str
    options: List[str]
    correct_option: int
    explanation: str
    skill: SkillType
    difficulty: Difficulty

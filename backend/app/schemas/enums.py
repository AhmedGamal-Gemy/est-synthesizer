"""EST Synthesizer - Shared Enum Definitions.

All enums inherit from ``LowerStrEnum`` which overrides
``_generate_next_value_`` so that ``auto()`` produces the lower-cased
member name (e.g. ``LONG`` → ``"long"``).  This keeps the source of truth
in one place and avoids hard-coding string literals in multiple files.
"""

from enum import Enum, auto


class LowerStrEnum(str, Enum):
    """Base enum where ``auto()`` values are the lower-cased member name."""

    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:
        return name.lower()


class PassageType(LowerStrEnum):
    """Classification of a passage by length/structure."""

    LONG = auto()   # "long"
    SHORT = auto()  # "short"


class PassageCategory(LowerStrEnum):
    """Content classification of a passage."""

    ESSAY = auto()          # "essay"
    NARRATIVE = auto()      # "narrative"
    SCIENTIFIC = auto()     # "scientific"
    HISTORY = auto()        # "history"
    ARGUMENTATIVE = auto()  # "argumentative"


class QuestionType(LowerStrEnum):
    """High-level question modality."""

    MULTIPLE_CHOICE = auto()  # "multiple_choice"


class SkillType(LowerStrEnum):
    """EST skill taxonomy. American English terminology."""

    # Writing
    CONVENTIONS_OF_STANDARD_ENGLISH = auto()  # "conventions_of_standard_english"
    SENTENCE_FORMATION = auto()               # "sentence_formation"
    PUNCTUATION = auto()                      # "punctuation"
    USAGE = auto()                            # "usage"
    TENSES = auto()                           # "tenses"
    PLACEMENT = auto()                        # "placement"
    ADD_DELETE = auto()                       # "add_delete"
    LOGICAL_INTRODUCTION = auto()             # "logical_introduction"

    # Reading
    INFORMATION_AND_IDEAS = auto()  # "information_and_ideas"
    RHETORIC = auto()               # "rhetoric"
    SYNTHESIS = auto()              # "synthesis"
    VOCABULARY_IN_CONTEXT = auto()  # "vocabulary_in_context"
    COMMAND_OF_EVIDENCE = auto()    # "command_of_evidence"
    GRAPH = auto()                  # "graph"


class Difficulty(LowerStrEnum):
    """Relative difficulty of a question."""

    EASY = auto()   # "easy"
    MEDIUM = auto()  # "medium"
    HARD = auto()   # "hard"


class DistractorRole(LowerStrEnum):
    """Pedagogical role assigned to each wrong answer choice.

    Exactly one ``BEST_ANSWER`` and one ``GOOD_NOT_BEST`` per question;
    the remaining two are ``COMPLETELY_WRONG``.
    """

    BEST_ANSWER = auto()      # "best_answer"
    GOOD_NOT_BEST = auto()    # "good_not_best"
    COMPLETELY_WRONG = auto() # "completely_wrong"


class QuestionFlag(LowerStrEnum):
    """American English quality flags raised during human review."""

    AMBIGUOUS = auto()             # "ambiguous"
    POORLY_PHRASED = auto()        # "poorly_phrased"
    OFF_TOPIC = auto()             # "off_topic"
    TOO_EASY = auto()              # "too_easy"
    TOO_HARD = auto()              # "too_hard"
    INCORRECT_ANSWER = auto()      # "incorrect_answer"
    UNCLEAR_DISTRACTORS = auto()   # "unclear_distractors"
    FACTUALLY_INCORRECT = auto()   # "factually_incorrect"


class JobStatus(LowerStrEnum):
    """Lifecycle status of a generation job."""

    PENDING = auto()      # "pending"
    QUEUED = auto()       # "queued"
    GENERATING = auto()   # "generating"
    ASSEMBLING = auto()   # "assembling"
    RENDERING = auto()    # "rendering"
    COMPLETED = auto()    # "completed"
    FAILED = auto()       # "failed"

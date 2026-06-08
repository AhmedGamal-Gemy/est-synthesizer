from fastapi import APIRouter
from backend.app.schemas.models import QuestionFeedback

router = APIRouter()

# This is the router, which tells FastAPI which URL paths to listen for.
# It acts like a dispatcher, sending requests to the correct functions.

@router.post("/api/tests/{test_id}/questions/{question_id}/feedback")
async def post_feedback(test_id: str, question_id: str, feedback: QuestionFeedback):
    # This function handles the POST request to submit feedback for a specific question.
    # 'test_id' and 'question_id' come from the URL, 'feedback' comes from the JSON body.
    
    # TODO: Implement - see QuestionFeedback in models.py
    # You will need to call the database function here to save the feedback object.
    
    raise NotImplementedError("post_feedback not implemented")

@router.get("/api/tests/{test_id}/feedback")
async def get_feedback(test_id: str):
    # This function handles the GET request to fetch all feedback for a specific test.
    # 'test_id' comes from the URL.
    
    # TODO: Implement - see QuestionFeedback in models.py
    # You will need to query the database and return a list of feedback records.
    
    raise NotImplementedError("get_feedback not implemented")

"""
SportyFY - Training AI Feature

Purpose:
This module provides logic for suggesting training plan adaptations based on 
User Feedback (Rating of Perceived Exertion - RPE). It helps trainees 
dynamically adjust their intensity for optimal progress and recovery.

Application Context:
Dynamic intelligence layer for the workout tracking feature.

Data Flow:
Trainee Feedback -> calculate_adaptation -> Suggested Next Workout Parameters
"""

from fastapi import APIRouter
from pydantic import BaseModel

# Initialize the router for this feature
router = APIRouter()


class TrainingFeedback(BaseModel):
    """
    Pydantic model representing the performance feedback from a completed session.
    
    Attributes:
        session_id (str): Reference to the completed training session.
        target_weight (float): The weight originally prescribed.
        actual_reps (int): The number of repetitions successfully completed.
        target_reps (int): The originally prescribed repetition target.
        rpe_score (int): Rating of Perceived Exertion (Scale 1-10).
    """
    session_id: str
    target_weight: float
    actual_reps: int
    target_reps: int
    rpe_score: int


class AdaptationSuggestion(BaseModel):
    """
    Pydantic model representing the suggested changes for the next identical session.
    
    Attributes:
        suggested_weight (float): Optimized weight for the next session.
        suggested_reps (int): Optimized repetition target.
        reasoning (str): Human-readable explanation for the adjustment.
    """
    suggested_weight: float
    suggested_reps: int
    reasoning: str


def calculate_adaptation(feedback: TrainingFeedback) -> AdaptationSuggestion:
    """
    Calculates the suggested sets/reps/weight for the next training session
    based on the user's RPE and actual performance vs targets.

    Args:
        feedback (TrainingFeedback): Data containing target vs actuals and RPE.

    Returns:
        AdaptationSuggestion: The calculated suggestion for the next session.
        
    Side Effects:
        - None (Pure functional logic).
    """
    new_weight = feedback.target_weight
    new_reps = feedback.target_reps
    reasoning = "Maintain current intensity."

    # Logic Branch: Failure to hit repetition targets.
    if feedback.actual_reps < feedback.target_reps:
        # If target reps weren't reached, reduce intensity to ensure recovery and form.
        new_weight = feedback.target_weight * 0.9  # Reduce weight by 10%
        reasoning = "Target reps not reached. Decreasing weight by 10%."
        
    # Logic Branch: High RPE (Safety First).
    elif feedback.rpe_score >= 9:
        # Even if targets were hit, a very high RPE suggests max effort.
        # Maintain or scale back to avoid overtraining.
        reasoning = "RPE is very high. Maintaining current weight to focus on recovery."
        
    # Logic Branch: Low RPE (Progressive Overload).
    elif feedback.rpe_score <= 6 and feedback.actual_reps >= feedback.target_reps:
        # If the workout felt easy (RPE <= 6) and targets were met, increase intensity.
        new_weight = feedback.target_weight * 1.05  # Increase weight by 5%
        new_reps = feedback.target_reps + 1
        reasoning = "RPE is low. Increasing weight by 5% and target reps by 1."

    return AdaptationSuggestion(
        suggested_weight=round(new_weight, 2),
        suggested_reps=new_reps,
        reasoning=reasoning
    )


@router.post("/adapt-plan", response_model=AdaptationSuggestion)
def adapt_training_plan(feedback: TrainingFeedback):
    """
    API Endpoint to process training feedback and return the next suggested parameters.
    
    Args:
        feedback (TrainingFeedback): The feedback payload containing performance metrics.

    Returns:
        AdaptationSuggestion: A JSON object containing the adapted parameters for the next workout.
    """
    # Simply delegate the calculation to the business logic function.
    suggestion = calculate_adaptation(feedback)
    return suggestion


# backend/app/models/feedback.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from datetime import datetime
from app.config.language_metadata import LanguageMetadata

class FeedbackMetrics(BaseModel):
    """Core feedback metrics"""
    satisfaction: int = Field(..., ge=1, le=5, description="Overall satisfaction")
    accuracy: int = Field(..., ge=1, le=5, description="Diagnosis accuracy")
    clarity: int = Field(..., ge=1, le=5, description="Communication clarity")
    language_quality: int = Field(..., ge=1, le=5, description="Translation quality")

class LanguageFeedback(BaseModel):
    """Language-specific feedback"""
    translation_quality: int = Field(..., ge=1, le=5)
    understanding: int = Field(..., ge=1, le=5)
    cultural_appropriateness: int = Field(..., ge=1, le=5)
    medical_term_clarity: int = Field(..., ge=1, le=5)

class FeedbackCreate(BaseModel):
    """Model for creating feedback"""
    consultation_id: str = Field(..., description="Associated consultation ID")
    metrics: FeedbackMetrics
    language_feedback: Optional[LanguageFeedback] = None
    comment: Optional[str] = None
    language: str = Field(default="en")
    
    # Only store essential metadata
    improvement_areas: Optional[List[str]] = None
    reported_issues: Optional[List[str]] = None

    @validator('language')
    def validate_language(cls, v):
        if not LanguageMetadata.is_language_supported(v):
            raise ValueError(f"Unsupported language: {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "consultation_id": "123e4567-e89b-12d3-a456-426614174000",
                "metrics": {
                    "satisfaction": 5,
                    "accuracy": 4,
                    "clarity": 5,
                    "language_quality": 4
                },
                "language_feedback": {
                    "translation_quality": 4,
                    "understanding": 5,
                    "cultural_appropriateness": 5,
                    "medical_term_clarity": 4
                },
                "comment": "Very helpful consultation!",
                "language": "en"
            }
        }

class FeedbackResponse(BaseModel):
    """Model for feedback response"""
    id: str
    consultation_id: str
    metrics: FeedbackMetrics
    language_feedback: Optional[LanguageFeedback]
    comment: Optional[str]
    language: str
    created_at: datetime
    
    # Analytics data (not stored permanently)
    analysis: Optional[Dict] = Field(None, exclude=True)
    sentiment_score: Optional[float] = Field(None, exclude=True)

class FeedbackAnalytics(BaseModel):
    """Analytics for feedback - temporary storage"""
    average_ratings: Dict[str, float]
    language_metrics: Dict[str, Dict[str, float]]
    improvement_suggestions: List[str]
    common_issues: List[Dict[str, any]]
    period: str
    generated_at: datetime
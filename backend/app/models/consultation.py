# backend/app/models/consultation.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum
from app.config.language_metadata import LanguageMetadata
from app.config.database import initialize_db
from fastapi import FastAPI, APIRouter

router = APIRouter()

@router.on_event("startup")
async def startup_event():
    await initialize_db()



class LanguagePreference(BaseModel):
    """Language preferences for consultation"""
    preferred: str = Field(..., description="Preferred language for communication")
    interface: str = Field(..., description="Interface language")
    auto_detect: bool = Field(default=True)

    @validator('preferred', 'interface')
    def validate_language(cls, v):
        if not LanguageMetadata.is_language_supported(v):
            raise ValueError(f"Unsupported language: {v}")
        return v

class UserVitals(BaseModel):
    """User vital statistics"""
    height: float = Field(..., gt=0, description="Height in cm")
    weight: float = Field(..., gt=0, description="Weight in kg")
    bmi: Optional[float] = Field(None, description="Calculated BMI")

    @validator('bmi', always=True)
    def calculate_bmi(cls, v, values):
        if 'height' in values and 'weight' in values:
            height_m = values['height'] / 100
            return round(values['weight'] / (height_m * height_m), 2)
        return v

class MedicalHistory(BaseModel):
    """Critical medical history"""
    conditions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    critical_notes: Optional[str] = None

class ConsultationCreate(BaseModel):
    """Data required to create consultation"""
    # Permanent Storage
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    age: int = Field(..., gt=0, lt=150)
    gender: str = Field(..., pattern="^(male|female|other)$")
    email: EmailStr
    mobile: str = Field(..., min_length=10)
    vitals: UserVitals
    language_preferences: LanguagePreference
    medical_history: Optional[MedicalHistory] = None

    # Optional/Temporary Storage
    device_info: Optional[Dict] = Field(None, exclude=True)  # Not for permanent storage
    location: Optional[Dict] = Field(None, exclude=True)     # Not for permanent storage
    session_metadata: Optional[Dict] = Field(None, exclude=True)  # Not for permanent storage

class ConsultationSummary(BaseModel):
    """Permanent consultation record"""
    # Core Identifiers
    consultation_id: str
    created_at: datetime
    completed_at: Optional[datetime]
    
    # User Information
    user_info: Dict = Field(..., description="Basic user info and vitals")
    medical_history: MedicalHistory
    
    # Critical Medical Data
    primary_symptoms: List[Dict] = Field(..., description="Key symptoms identified")
    diagnosis: Optional[Dict] = Field(None, description="Final diagnosis if available")
    recommendations: List[str] = Field(default_factory=list)
    prescriptions: Optional[List[Dict]] = None
    
    # Safety Flags
    emergency_incidents: List[Dict] = Field(default_factory=list)
    critical_alerts: List[str] = Field(default_factory=list)
    
    # Reference Data
    language: str
    consultation_notes: Optional[str] = None

class MessageContent(BaseModel):
    """Message content with storage optimization"""
    text: str
    language: str
    medical_terms: Optional[List[str]] = None
    requires_attention: bool = False
    
    # Temporary data - not for permanent storage
    translated_text: Optional[str] = Field(None, exclude=True)
    confidence_score: Optional[float] = Field(None, exclude=True)
    processing_metadata: Optional[Dict] = Field(None, exclude=True)

class ConsultationMessage(BaseModel):
    """Optimized message storage"""
    type: str = Field(..., pattern="^(user|bot)$")
    content: MessageContent
    timestamp: datetime
    
    # Optional flags for retention
    retain: bool = Field(default=False, description="Flag for permanent storage")
    critical: bool = Field(default=False, description="Contains critical medical info")

class ActiveConsultation(BaseModel):
    """Active consultation session data"""
    consultation_id: str
    user_info: Dict
    status: str = Field(..., pattern="^(started|active|completed|terminated)$")
    language_preferences: LanguagePreference
    
    # Session data (temporary)
    messages: List[ConsultationMessage] = []
    current_context: Optional[Dict] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_activity: datetime

    class Config:
        # Exclude temporary fields from serialization
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
        # Fields to exclude from permanent storage
        exclude = {
            'current_context',
            'temporary_data',
            'session_metadata'
        }

class ConsultationUpdate(BaseModel):
    """Model for updating consultation data"""
    language_preferences: Optional[LanguagePreference] = None
    vitals: Optional[UserVitals] = None
    status: Optional[str] = Field(None, pattern="^(active|completed|terminated)$")
    
    @validator('status')
    def validate_status(cls, v):
        if v not in ['active', 'completed', 'terminated']:
            raise ValueError('Invalid status')
        return v
    
class ConsultationResponse(BaseModel):
    """API response model for consultation endpoints"""
    consultation_id: str
    user_details: Dict
    status: str
    language_preferences: LanguagePreference
    messages: List[ConsultationMessage] = []
    created_at: datetime
    updated_at: datetime
    last_activity: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
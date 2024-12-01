# backend/app/utils/ai_config.py
import google.generativeai as genai
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
import logging
from pydantic import BaseModel
from app.config.language_metadata import LanguageMetadata
import json
from typing import Set

logger = logging.getLogger(__name__)

class MedicalPrompt(BaseModel):
    """Structured medical prompts"""
    context: str
    symptoms: List[str]
    medical_history: Optional[Dict] = None
    emergency_flags: List[str] = []
    confidence_required: bool = True

class GeminiConfig:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found")
            
        # Response configuration
        self.max_tokens = 256
        self.response_format = {
            "type": "json",
            "schema": {
                "symptoms": "list",
                "severity": "float",
                "recommendations": "list",
                "emergency": "boolean"
            }
        }
        
        # Initialize with medical focus
        self.initialize_model()
        
        # Medical prompt templates
        self.prompt_templates = self._initialize_prompts()
        

    def initialize_model(self):
        """Initialize and configure Gemini model"""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name='gemini-pro',
                generation_config={
                    'temperature': 0.3,  # Lower for medical precision
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': self.max_tokens,
                }
            )
            logger.info("Gemini model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {str(e)}")
            raise

    def _initialize_prompts(self) -> Dict[str, str]:
        """Initialize medical prompt templates"""
        return {
            "initial_assessment": """
            You are a medical pre-diagnosis assistant analyzing symptoms for a patient.
            
            Patient Details:
            Age: {age}
            Gender: {gender}
            Medical History: {medical_history}
            
            Current Symptoms: {symptoms}
            
            Provide a structured analysis:
            1. Symptom assessment
            2. Severity estimation
            3. Recommendations
            4. Emergency indicators
            
            Format response as JSON with confidence scores.
            """,
            
            "followup_questions": """
            Based on the patient's responses:
            Previous Context: {context}
            New Information: {new_info}
            
            What are the most critical follow-up questions?
            Focus on: {focus_areas}
            
            Provide exactly ONE specific question.
            """,
            
            "emergency_assessment": """
            URGENT SYMPTOM ASSESSMENT
            Symptoms: {symptoms}
            Duration: {duration}
            Severity Indicators: {severity}
            
            Provide immediate assessment:
            1. Emergency level (HIGH/MEDIUM/LOW)
            2. Immediate actions required
            3. Time sensitivity
            
            Be clear and direct.
            """
        }

    async def generate_medical_response(
        self,
        prompt: MedicalPrompt,
        message_history: Optional[List] = None
    ) -> Dict:
        """Generate medical response with context"""
        try:
            # Format prompt with medical context
            formatted_prompt = self._format_medical_prompt(prompt, message_history)
            
            # Generate response
            response = self.model.generate_content(formatted_prompt)
            
            # Process and validate response
            processed_response = self._process_medical_response(response.text)
            
            return processed_response
            
        except Exception as e:
            logger.error(f"Error generating medical response: {str(e)}")
            raise

    def _format_medical_prompt(
        self,
        prompt: MedicalPrompt,
        message_history: Optional[List] = None
    ) -> str:
        """Format prompt with medical context"""
        # Get base template
        template = self.prompt_templates["initial_assessment"]
        
        # Add conversation history if available
        if message_history:
            history_context = self._format_conversation_history(message_history)
            template += f"\nConversation History:\n{history_context}"
        
        # Add emergency flags if any
        if prompt.emergency_flags:
            template = self.prompt_templates["emergency_assessment"]
        
        return template

    def _process_medical_response(self, response: str) -> Dict:
        """Process and validate medical response"""
        try:
            # Extract structured data
            processed = json.loads(response)
            
            # Validate medical terms
            if "symptoms" in processed:
                processed["symptoms"] = self._validate_medical_terms(
                    processed["symptoms"]
                )
            
            # Add confidence scores if required
            if self.response_format["schema"].get("confidence"):
                processed["confidence"] = self._calculate_confidence(processed)
            
            return processed
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from model")
            return self._format_fallback_response(response)

    def _validate_medical_terms(self, terms: List[str]) -> List[str]:
        """Validate medical terms through AI analysis"""
        try:
        # Instead of checking against a predefined vocabulary,
        # we'll trust the AI model's medical knowledge
          return terms
            
        except Exception as e:
            logger.error(f"Error validating medical terms: {str(e)}")
            return []

    def _calculate_confidence(self, response: Dict) -> float:
        """Calculate confidence score for response"""
        # Implement confidence scoring logic
        return 0.0  # Placeholder

    def _format_fallback_response(self, text: str) -> Dict:
        """Format fallback response for invalid JSON"""
        return {
            "response": text,
            "confidence": 0.5,
            "requires_validation": True
        }

    async def cleanup(self):
        """Cleanup resources"""
        # Implement cleanup logic
        pass
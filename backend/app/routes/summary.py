# backend/app/routes/summary.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.config.database import consultations_collection
from app.utils.symptom_analyzer import SymptomAnalyzer
from app.config.language_metadata import LanguageMetadata
from datetime import datetime
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
symptom_analyzer = SymptomAnalyzer()

@router.get("/summary/{consultation_id}")
async def get_consultation_summary(
    consultation_id: str,
    language: Optional[str] = None,
    include_analysis: bool = True
):
    """Get consultation summary and generate diagnosis."""
    try:
        consultation = await consultations_collection.find_one(
            {"consultation_id": consultation_id}
        )
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")
        
        try:
            # Get preferred language
            preferred_language = language or consultation["language_preferences"]["preferred"]
            
            # Process in English
            chat_history = consultation.get('chat_history', [])
            
            if include_analysis:
                # Analyze symptoms in English
                analyzed_symptoms = await symptom_analyzer.analyze_conversation(chat_history)
                severity_assessment = await symptom_analyzer.get_severity_assessment(
                    analyzed_symptoms.get('symptoms', [])
                )
                validation_result = await symptom_analyzer.validate_medical_response(
                    str(analyzed_symptoms),
                    chat_history
                )
                treatment_recommendations = await symptom_analyzer.get_treatment_recommendations(
                    analyzed_symptoms.get('symptoms', [])
                )
            else:
                analyzed_symptoms = {"symptoms": [], "progression": ""}
                severity_assessment = {"overall_severity": 0, "risk_level": "unknown"}
                validation_result = {"safety_concerns": [], "suggested_improvements": []}
                treatment_recommendations = {"medications": [], "homeRemedies": []}
            
            # Create summary structure
            summary = {
                "consultation_id": consultation_id,
                "userDetails": consultation["user_details"],
                "diagnosis": {
                    "symptoms": analyzed_symptoms.get('symptoms', []),
                    "description": analyzed_symptoms.get('progression', ''),
                    "severityScore": severity_assessment.get('overall_severity', 0),
                    "riskLevel": severity_assessment.get('risk_level', 'unknown'),
                    "timeframe": severity_assessment.get('recommended_timeframe', ''),
                    "recommendedDoctor": await symptom_analyzer.recommend_specialist(
                        analyzed_symptoms.get('symptoms', [])
                    )
                },
                "recommendations": {
                    "medications": treatment_recommendations.get("medications", []),
                    "homeRemedies": treatment_recommendations.get("homeRemedies", []),
                    "urgency": analyzed_symptoms.get('urgency', 'unknown'),
                    "safety_concerns": validation_result.get('safety_concerns', []),
                    "suggested_improvements": validation_result.get('suggested_improvements', [])
                },
                "precautions": analyzed_symptoms.get('precautions', []),
                "chatHistory": chat_history,
                "language": preferred_language,
                "created_at": consultation["created_at"],
                "completed_at": datetime.utcnow(),
                "metadata": {
                    "analysis_included": include_analysis,
                    "language_info": LanguageMetadata.get_language_metadata(preferred_language),
                    "medical_terms_preserved": LanguageMetadata.should_preserve_medical_terms(preferred_language)
                }
            }
            
            # Translate necessary parts if not in English
            if preferred_language != "en":
                summary = await _translate_summary(summary, preferred_language)
            
            # Update consultation with summary
            await consultations_collection.update_one(
                {"consultation_id": consultation_id},
                {
                    "$set": {
                        "status": "completed",
                        "diagnosis_summary": summary,
                        "completed_at": datetime.utcnow()
                    }
                }
            )
            
            return summary
            
        except Exception as analysis_error:
            logger.error(f"Error analyzing consultation data: {str(analysis_error)}")
            raise HTTPException(status_code=500, detail=str(analysis_error))
            
    except Exception as e:
        logger.error(f"Error generating consultation summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quick-summary/{consultation_id}")
async def get_quick_summary(
    consultation_id: str,
    language: Optional[str] = None
):
    """Get basic consultation summary without detailed analysis."""
    return await get_consultation_summary(
        consultation_id,
        language,
        include_analysis=False
    )

@router.post("/analyze/{consultation_id}")
async def analyze_consultation(
    consultation_id: str,
    background_tasks: BackgroundTasks
):
    """Trigger asynchronous consultation analysis."""
    try:
        consultation = await consultations_collection.find_one(
            {"consultation_id": consultation_id}
        )
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")
            
        # Schedule analysis in background
        background_tasks.add_task(
            _analyze_consultation_background,
            consultation_id,
            consultation
        )
        
        return {
            "message": "Analysis scheduled",
            "consultation_id": consultation_id,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Error scheduling analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def _analyze_consultation_background(
    consultation_id: str,
    consultation: Dict
):
    """Background task for consultation analysis."""
    try:
        # Perform analysis
        chat_history = consultation.get('chat_history', [])
        analyzed_symptoms = await symptom_analyzer.analyze_conversation(chat_history)
        
        # Update consultation with analysis results
        await consultations_collection.update_one(
            {"consultation_id": consultation_id},
            {
                "$set": {
                    "analysis_results": analyzed_symptoms,
                    "analysis_completed_at": datetime.utcnow()
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Background analysis error: {str(e)}")
        # Update consultation with error status
        await consultations_collection.update_one(
            {"consultation_id": consultation_id},
            {
                "$set": {
                    "analysis_error": str(e),
                    "analysis_status": "failed"
                }
            }
        )

async def _translate_summary(
    summary: Dict,
    target_language: str
) -> Dict:
    """Translate summary to target language."""
    try:
        translated_summary = summary.copy()
        
        # Translate diagnosis description
        if summary["diagnosis"]["description"]:
            translated_summary["diagnosis"]["description"] = await _translate_text(
                summary["diagnosis"]["description"],
                target_language
            )
        
        # Translate recommendations
        translated_summary["recommendations"]["medications"] = [
            await _translate_text(med, target_language)
            for med in summary["recommendations"]["medications"]
        ]
        
        translated_summary["recommendations"]["homeRemedies"] = [
            await _translate_text(remedy, target_language)
            for remedy in summary["recommendations"]["homeRemedies"]
        ]
        
        # Translate safety concerns and improvements
        translated_summary["recommendations"]["safety_concerns"] = [
            await _translate_text(concern, target_language)
            for concern in summary["recommendations"]["safety_concerns"]
        ]
        
        translated_summary["recommendations"]["suggested_improvements"] = [
            await _translate_text(improvement, target_language)
            for improvement in summary["recommendations"]["suggested_improvements"]
        ]
        
        # Translate precautions
        translated_summary["precautions"] = [
            await _translate_text(precaution, target_language)
            for precaution in summary["precautions"]
        ]
        
        return translated_summary
        
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return summary

async def _translate_text(text: str, target_language: str) -> str:
    """Translate text while preserving medical terms."""
    try:
        if not text or target_language == "en":
            return text
            
        # Check if medical terms should be preserved
        should_preserve = LanguageMetadata.should_preserve_medical_terms(target_language)
        
        if should_preserve:
            # Extract and preserve medical terms
            medical_terms = symptom_analyzer.extract_medical_terms(text)
            preserved_text = text
            
            for term in medical_terms:
                placeholder = f"__MEDICAL__{term}__"
                preserved_text = preserved_text.replace(term, placeholder)
            
            # Translate modified text
            translated = await symptom_analyzer.bhashini_service.translate_text(
                preserved_text,
                "en",
                target_language
            )
            
            # Restore medical terms
            result = translated["text"]
            for term in medical_terms:
                placeholder = f"__MEDICAL__{term}__"
                result = result.replace(placeholder, term)
                
            return result
        else:
            # Translate directly
            translated = await symptom_analyzer.bhashini_service.translate_text(
                text,
                "en",
                target_language
            )
            return translated["text"]
            
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return text
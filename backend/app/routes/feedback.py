# backend/app/routes/feedback.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.feedback import (
    FeedbackCreate,
    FeedbackResponse,
    FeedbackAnalytics
)
from app.config.database import consultations_collection
from app.config.language_metadata import LanguageMetadata
from datetime import datetime
import uuid
import logging
from typing import Optional, Dict, List
from datetime import timedelta
from collections import defaultdict, Counter


logger = logging.getLogger(__name__)
router = APIRouter()

async def process_feedback_analytics(feedback_data: Dict):
    """Process feedback analytics in background"""
    try:
        # Process analytics asynchronously
        # Store only essential metrics
        analytics = {
            "metrics": feedback_data["metrics"],
            "timestamp": datetime.utcnow(),
            "language": feedback_data["language"]
        }
        
        # Update analytics collection with minimal data
        await consultations_collection.update_one(
            {"consultation_id": feedback_data["consultation_id"]},
            {"$push": {"feedback_analytics": analytics}}
        )
    except Exception as e:
        logger.error(f"Error processing feedback analytics: {str(e)}")

@router.post("/submit", response_model=FeedbackResponse)
async def submit_feedback(
    feedback: FeedbackCreate,
    background_tasks: BackgroundTasks
):
    """Submit feedback with language support"""
    try:
        # Verify consultation exists
        consultation = await consultations_collection.find_one(
            {"consultation_id": feedback.consultation_id}
        )
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")

        # Create feedback document
        feedback_id = str(uuid.uuid4())
        feedback_doc = {
            "id": feedback_id,
            **feedback.dict(exclude_none=True),
            "created_at": datetime.utcnow()
        }

        # Store only essential feedback data
        result = await consultations_collection.update_one(
            {"consultation_id": feedback.consultation_id},
            {
                "$set": {
                    "feedback": feedback_doc,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Failed to submit feedback")

        # Process analytics in background
        background_tasks.add_task(
            process_feedback_analytics,
            feedback_doc
        )

        return FeedbackResponse(**feedback_doc)

    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{consultation_id}", response_model=FeedbackResponse)
async def get_feedback(consultation_id: str):
    """Get feedback for specific consultation"""
    consultation = await consultations_collection.find_one(
        {"consultation_id": consultation_id},
        {"feedback": 1}
    )
    
    if not consultation or "feedback" not in consultation:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    return FeedbackResponse(**consultation["feedback"])

@router.get("/stats/{consultation_id}")
async def get_feedback_stats(
    consultation_id: str,
    language: Optional[str] = None
):
    """Get statistical analysis of feedback"""
    try:
        consultation = await consultations_collection.find_one(
            {"consultation_id": consultation_id},
            {"feedback": 1, "feedback_analytics": 1}
        )
        
        if not consultation or "feedback" not in consultation:
            raise HTTPException(status_code=404, detail="Feedback not found")
            
        feedback = consultation["feedback"]
        
        # Calculate essential stats only
        stats = {
            "metrics": {
                "satisfaction": feedback["metrics"]["satisfaction"],
                "accuracy": feedback["metrics"]["accuracy"]
            },
            "language_metrics": feedback.get("language_feedback", {}),
            "has_comment": bool(feedback.get("comment")),
            "feedback_date": feedback["created_at"]
        }
        
        # Add language-specific stats if requested
        if language and language in LanguageMetadata.get_supported_languages():
            stats["language_specific"] = {
                "name": LanguageMetadata.get_language_name(language),
                "metrics": feedback.get("language_feedback", {})
            }
        
        return stats

    except Exception as e:
        logger.error(f"Error getting feedback stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{consultation_id}")
async def delete_feedback(consultation_id: str):
    """Delete feedback for specific consultation"""
    try:
        result = await consultations_collection.update_one(
            {"consultation_id": consultation_id},
            {
                "$unset": {"feedback": ""},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Feedback not found")
            
        return {"message": "Feedback deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/language/{language}")
async def get_language_feedback_analytics(
    language: str,
    period: Optional[str] = "all"
):
    """Get language-specific feedback analytics"""
    try:
        if not LanguageMetadata.is_language_supported(language):
            raise HTTPException(status_code=400, detail="Unsupported language")

        pipeline = [
            {"$match": {"feedback.language": language}},
            {"$project": {
                "metrics": "$feedback.metrics",
                "language_feedback": "$feedback.language_feedback",
                "created_at": "$feedback.created_at"
            }}
        ]

        results = await consultations_collection.aggregate(pipeline).to_list(None)

        # Process only essential analytics
        analytics = {
            "language": {
                "code": language,
                "name": LanguageMetadata.get_language_name(language)
            },
            "metrics": _calculate_language_metrics(results),
            "period": period,
            "generated_at": datetime.utcnow()
        }

        return analytics

    except Exception as e:
        logger.error(f"Error getting language analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _calculate_language_metrics(results: List[Dict]) -> Dict:
    """Calculate essential language metrics"""
    if not results:
        return {}

    metrics = {
        "translation_quality": 0,
        "understanding": 0,
        "count": len(results)
    }

    for result in results:
        if "language_feedback" in result:
            metrics["translation_quality"] += result["language_feedback"].get("translation_quality", 0)
            metrics["understanding"] += result["language_feedback"].get("understanding", 0)

    # Calculate averages
    for key in ["translation_quality", "understanding"]:
        metrics[key] = round(metrics[key] / metrics["count"], 2)

    return metrics

@router.get("/analytics", response_model=FeedbackAnalytics)
async def get_comprehensive_analytics(
    language: Optional[str] = None,
    period: str = "last_30_days",
    consultation_type: Optional[str] = None
):
    """Get comprehensive feedback analytics"""
    try:
        # Build aggregation pipeline
        pipeline = [
            {
                "$match": {
                    "feedback": {"$exists": True},
                    "feedback.created_at": {
                        "$gte": _get_period_start_date(period)
                    }
                }
            },
            {
                "$project": {
                    "feedback": 1,
                    "consultation_id": 1,
                    "language_preferences": 1
                }
            }
        ]

        if language:
            pipeline[0]["$match"]["feedback.language"] = language

        results = await consultations_collection.aggregate(pipeline).to_list(None)

        # Process analytics
        analytics = await _process_comprehensive_analytics(results, language)
        
        return FeedbackAnalytics(
            average_ratings=analytics["ratings"],
            language_metrics=analytics["language_metrics"],
            improvement_suggestions=analytics["suggestions"],
            common_issues=analytics["issues"],
            period=period,
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/language-comparison")
async def get_language_comparison_analytics(
    languages: Optional[List[str]] = None,
    period: str = "last_30_days"
):
    """Compare feedback across different languages"""
    try:
        # Use provided languages or all supported languages
        target_languages = (languages if languages 
                          else LanguageMetadata.get_supported_languages())
        
        # Validate languages
        for lang in target_languages:
            if not LanguageMetadata.is_language_supported(lang):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported language: {lang}"
                )

        # Get analytics for each language
        comparisons = {}
        for lang in target_languages:
            analytics = await get_comprehensive_analytics(
                language=lang,
                period=period
            )
            comparisons[lang] = {
                "name": LanguageMetadata.get_language_name(lang),
                "metrics": analytics.dict(exclude={'period', 'generated_at'})
            }

        return {
            "comparisons": comparisons,
            "period": period,
            "generated_at": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error generating language comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def _process_comprehensive_analytics(
    results: List[Dict],
    language: Optional[str]
) -> Dict:
    """Process comprehensive analytics from feedback data"""
    analytics = {
        "ratings": defaultdict(list),
        "language_metrics": defaultdict(dict),
        "suggestions": [],
        "issues": []
    }

    for result in results:
        feedback = result.get("feedback", {})
        
        # Process ratings
        metrics = feedback.get("metrics", {})
        for key, value in metrics.items():
            analytics["ratings"][key].append(value)

        # Process language feedback
        lang_feedback = feedback.get("language_feedback", {})
        if lang_feedback:
            lang = feedback.get("language", "en")
            if lang not in analytics["language_metrics"]:
                analytics["language_metrics"][lang] = defaultdict(list)
            
            for key, value in lang_feedback.items():
                analytics["language_metrics"][lang][key].append(value)

        # Process improvement areas and issues
        if feedback.get("improvement_areas"):
            analytics["suggestions"].extend(feedback["improvement_areas"])
        if feedback.get("reported_issues"):
            analytics["issues"].extend(feedback["reported_issues"])

    # Calculate averages and process final analytics
    processed = {
        "ratings": {
            k: round(sum(v) / len(v), 2) if v else 0
            for k, v in analytics["ratings"].items()
        },
        "language_metrics": {
            lang: {
                k: round(sum(v) / len(v), 2) if v else 0
                for k, v in metrics.items()
            }
            for lang, metrics in analytics["language_metrics"].items()
        },
        "suggestions": _process_common_items(analytics["suggestions"]),
        "issues": _process_common_items(analytics["issues"])
    }

    return processed

def _process_common_items(items: List[str]) -> List[Dict]:
    """Process and count common items"""
    counter = Counter(items)
    return [
        {"item": item, "count": count}
        for item, count in counter.most_common(5)
    ]

def _get_period_start_date(period: str) -> datetime:
    """Get start date for analytics period"""
    now = datetime.utcnow()
    periods = {
        "last_24_hours": timedelta(days=1),
        "last_7_days": timedelta(days=7),
        "last_30_days": timedelta(days=30),
        "last_90_days": timedelta(days=90)
    }
    return now - periods.get(period, periods["last_30_days"])

# Update existing get_feedback_stats route to use FeedbackAnalytics
@router.get("/stats/{consultation_id}", response_model=FeedbackAnalytics)
async def get_feedback_stats(
    consultation_id: str,
    language: Optional[str] = None
):
    """Get statistical analysis of feedback with analytics model"""
    try:
        consultation = await consultations_collection.find_one(
            {"consultation_id": consultation_id},
            {"feedback": 1, "feedback_analytics": 1}
        )
        
        if not consultation or "feedback" not in consultation:
            raise HTTPException(status_code=404, detail="Feedback not found")
            
        feedback = consultation["feedback"]
        
        # Process analytics using the FeedbackAnalytics model
        analytics = await _process_comprehensive_analytics(
            [consultation],
            language
        )
        
        return FeedbackAnalytics(
            average_ratings=analytics["ratings"],
            language_metrics=analytics["language_metrics"],
            improvement_suggestions=analytics["suggestions"],
            common_issues=analytics["issues"],
            period="single_consultation",
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting feedback stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
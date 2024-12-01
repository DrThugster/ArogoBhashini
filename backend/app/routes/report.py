# backend/app/routes/report.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from app.config.database import consultations_collection
from app.utils.report_generator import ReportGeneratorService
from app.routes.summary import get_consultation_summary
from app.config.language_metadata import LanguageMetadata
from typing import Optional
import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
report_generator = ReportGeneratorService()

@router.get("/{consultation_id}")
async def get_consultation_report(
    background_tasks: BackgroundTasks,
    consultation_id: str,
    language: Optional[str] = None
):
    """Generate and download PDF report."""
    try:
        consultation = await consultations_collection.find_one(
            {"consultation_id": consultation_id}
        )
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")
        
        try:
            # Get or generate summary
            if "diagnosis_summary" not in consultation:
                summary = await get_consultation_summary(consultation_id)
            else:
                summary = consultation["diagnosis_summary"]
            
            # Ensure symptoms data is available
            if "symptoms" not in summary and "diagnosis" in summary:
                summary["symptoms"] = summary["diagnosis"].get("symptoms", [])
            
            # Get user's preferred language for the report
            report_language = language or consultation["language_preferences"]["preferred"]
            
            # Validate language support
            if not LanguageMetadata.is_language_supported(report_language):
                raise HTTPException(
                    status_code=400,
                    detail=f"Language {report_language} not supported"
                )
            
            # Generate PDF asynchronously
            pdf_buffer = await report_generator.create_medical_report(
                summary,
                report_language
            )
            
            # Schedule cleanup in background
            background_tasks.add_task(
                cleanup_report_resources,
                consultation_id
            )
            
            return StreamingResponse(
                io.BytesIO(pdf_buffer.getvalue()),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": (
                        f"attachment; "
                        f"filename=consultation-report-{consultation_id}.pdf"
                    )
                }
            )
            
        except Exception as report_error:
            logger.error(f"Error generating PDF report: {str(report_error)}")
            raise HTTPException(status_code=500, detail=str(report_error))
            
    except Exception as e:
        logger.error(f"Error handling report request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview/{consultation_id}")
async def preview_report(
    consultation_id: str,
    language: Optional[str] = None
):
    """Generate report preview data."""
    try:
        consultation = await consultations_collection.find_one(
            {"consultation_id": consultation_id}
        )
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")
            
        # Get summary data
        summary = consultation.get("diagnosis_summary")
        if not summary:
            summary = await get_consultation_summary(consultation_id)
        
        # Get preview language
        preview_language = language or consultation["language_preferences"]["preferred"]
        
        # Generate preview data
        preview_data = {
            "consultation_id": consultation_id,
            "patient_info": {
                "name": f"{consultation['user_details']['firstName']} {consultation['user_details']['lastName']}",
                "age": consultation['user_details']['age'],
                "gender": consultation['user_details']['gender']
            },
            "medical_data": {
                "symptoms": summary.get("symptoms", []),
                "diagnosis": summary.get("diagnosis", {}),
                "recommendations": summary.get("recommendations", {})
            },
            "language": {
                "code": preview_language,
                "name": LanguageMetadata.get_language_name(preview_language)
            },
            "preview_generated_at": datetime.utcnow().isoformat()
        }
        
        return JSONResponse(content=preview_data)
        
    except Exception as e:
        logger.error(f"Error generating report preview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{consultation_id}")
async def get_report_status(consultation_id: str):
    """Get report generation status."""
    try:
        consultation = await consultations_collection.find_one(
            {"consultation_id": consultation_id},
            {"report_status": 1}
        )
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")
            
        report_status = consultation.get("report_status", {})
        
        return {
            "status": report_status.get("status", "not_started"),
            "progress": report_status.get("progress", 0),
            "last_updated": report_status.get("last_updated"),
            "error": report_status.get("error")
        }
        
    except Exception as e:
        logger.error(f"Error getting report status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def cleanup_report_resources(consultation_id: str):
    """Cleanup temporary report resources."""
    try:
        # Cleanup any temporary files or resources
        pass
    except Exception as e:
        logger.error(f"Error cleaning up report resources: {str(e)}")
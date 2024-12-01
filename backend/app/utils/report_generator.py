# backend/app/utils/report_generator.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import logging
import asyncio
from typing import Dict, Optional, List
from app.config.language_metadata import LanguageMetadata
from app.services.bhashini_service import BhashiniService

logger = logging.getLogger(__name__)

class ReportGeneratorService:
    def __init__(self):
        self.bhashini_service = BhashiniService()
        self.template_cache = {}
        self.style_cache = {}
        
        # Resource management
        self.report_semaphore = asyncio.Semaphore(5)
        self.max_retries = 3
        
        # Initialize templates and styles
        self._initialize_resources()

    def _initialize_resources(self):
        """Initialize report resources"""
        try:
            self.styles = getSampleStyleSheet()
            
            # Cache common styles
            for lang_code in LanguageMetadata.get_supported_languages():
                self.style_cache[lang_code] = self._create_language_styles(lang_code)
                
            # Cache templates
            self._initialize_templates()
            
        except Exception as e:
            logger.error(f"Error initializing resources: {str(e)}")
            raise

    def _create_language_styles(self, language: str) -> Dict:
        """Create language-specific styles"""
        lang_meta = LanguageMetadata.get_language_metadata(language)
        
        # Get script-specific settings
        is_rtl = lang_meta.get("rtl", False)
        font_family = lang_meta.get("font_family", "Helvetica")
        
        return {
            "title": ParagraphStyle(
                f"Title_{language}",
                parent=self.styles["Title"],
                fontName=font_family,
                alignment=2 if is_rtl else 0
            ),
            "heading": ParagraphStyle(
                f"Heading_{language}",
                parent=self.styles["Heading1"],
                fontName=font_family,
                alignment=2 if is_rtl else 0
            ),
            "normal": ParagraphStyle(
                f"Normal_{language}",
                parent=self.styles["Normal"],
                fontName=font_family,
                alignment=2 if is_rtl else 0
            )
        }

    def _initialize_templates(self):
        """Initialize report templates"""
        self.template_cache = {
            "medical_report": {
                "sections": [
                    "patient_info",
                    "symptoms",
                    "diagnosis",
                    "recommendations"
                ],
                "layout": self._get_report_layout()
            }
        }

    async def create_medical_report(
        self,
        consultation_data: Dict,
        language: str,
        include_graphs: bool = True
    ) -> BytesIO:
        """Create medical report with language support"""
        async with self.report_semaphore:
            try:
                # Initialize buffer
                buffer = BytesIO()
                
                # Get language-specific styles
                styles = self.style_cache.get(language, self._create_language_styles(language))
                
                # Create document
                doc = SimpleDocTemplate(
                    buffer,
                    pagesize=letter,
                    rightMargin=72,
                    leftMargin=72,
                    topMargin=72,
                    bottomMargin=72
                )
                
                # Generate content
                story = await self._generate_report_content(
                    consultation_data,
                    language,
                    styles,
                    include_graphs
                )
                
                # Build document
                doc.build(story)
                buffer.seek(0)
                return buffer
                
            except Exception as e:
                logger.error(f"Error creating medical report: {str(e)}")
                raise

    async def _generate_report_content(
        self,
        data: Dict,
        language: str,
        styles: Dict,
        include_graphs: bool
    ) -> List:
        """Generate report content with translations"""
        story = []
        
        # Add header
        header_text = await self._translate_text("Medical Consultation Report", language)
        story.append(Paragraph(header_text, styles["title"]))
        story.append(Spacer(1, 20))
        
        # Add patient information
        story.extend(await self._create_patient_section(data, language, styles))
        
        # Add symptoms and diagnosis
        story.extend(await self._create_medical_section(data, language, styles))
        
        # Add recommendations
        story.extend(await self._create_recommendations_section(data, language, styles))
        
        # Add graphs if requested
        if include_graphs:
            story.extend(await self._create_graphs_section(data, language, styles))
        
        # Add footer
        story.extend(await self._create_footer(language, styles))
        
        return story

    async def _create_patient_section(
        self,
        data: Dict,
        language: str,
        styles: Dict
    ) -> List:
        """Create patient information section"""
        section = []
        
        try:
            # Translate section title
            title = await self._translate_text("Patient Information", language)
            section.append(Paragraph(title, styles["heading"]))
            section.append(Spacer(1, 10))
            
            # Prepare patient data
            patient_data = [
                [await self._translate_text("Name", language), 
                 f"{data['user_details']['firstName']} {data['user_details']['lastName']}"],
                [await self._translate_text("Age", language), 
                 str(data['user_details']['age'])],
                [await self._translate_text("Gender", language), 
                 await self._translate_text(data['user_details']['gender'], language)],
            ]
            
            # Create table
            table = Table(patient_data)
            table.setStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('PADDING', (0, 0), (-1, -1), 6)
            ])
            
            section.append(table)
            section.append(Spacer(1, 20))
            
            return section
            
        except Exception as e:
            logger.error(f"Error creating patient section: {str(e)}")
            return []

    async def _create_medical_section(
        self,
        data: Dict,
        language: str,
        styles: Dict
    ) -> List:
        """Create medical information section"""
        section = []
        
        try:
            # Translate section title
            title = await self._translate_text("Medical Assessment", language)
            section.append(Paragraph(title, styles["heading"]))
            section.append(Spacer(1, 10))
            
            # Add symptoms
            symptoms_title = await self._translate_text("Reported Symptoms", language)
            section.append(Paragraph(symptoms_title, styles["normal"]))
            
            for symptom in data.get('symptoms', []):
                # Preserve medical terms if needed
                symptom_text = symptom['name']
                if not LanguageMetadata.should_preserve_medical_terms(language):
                    symptom_text = await self._translate_text(symptom_text, language)
                
                section.append(
                    Paragraph(
                        f"• {symptom_text}: {symptom.get('severity', 'N/A')}/10",
                        styles["normal"]
                    )
                )
            
            section.append(Spacer(1, 10))
            
            # Add diagnosis if available
            if 'diagnosis' in data:
                diagnosis_title = await self._translate_text("Diagnosis", language)
                section.append(Paragraph(diagnosis_title, styles["heading"]))
                
                diagnosis_text = await self._translate_text(
                    data['diagnosis'].get('description', ''),
                    language
                )
                section.append(Paragraph(diagnosis_text, styles["normal"]))
            
            return section
            
        except Exception as e:
            logger.error(f"Error creating medical section: {str(e)}")
            return []

    async def _create_recommendations_section(
        self,
        data: Dict,
        language: str,
        styles: Dict
    ) -> List:
        """Create recommendations section"""
        section = []
        
        try:
            title = await self._translate_text("Recommendations", language)
            section.append(Paragraph(title, styles["heading"]))
            section.append(Spacer(1, 10))
            
            for rec in data.get('recommendations', []):
                translated_rec = await self._translate_text(rec, language)
                section.append(Paragraph(f"• {translated_rec}", styles["normal"]))
            
            return section
            
        except Exception as e:
            logger.error(f"Error creating recommendations section: {str(e)}")
            return []

    async def _create_graphs_section(
        self,
        data: Dict,
        language: str,
        styles: Dict
    ) -> List:
        """Create graphs section with translations"""
        section = []
        
        try:
            # Create symptoms severity graph
            if data.get('symptoms'):
                graph_buffer = await self._create_symptoms_graph(
                    data['symptoms'],
                    language
                )
                
                if graph_buffer:
                    section.append(Image(graph_buffer, width=6*inch, height=4*inch))
                    section.append(Spacer(1, 10))
            
            return section
            
        except Exception as e:
            logger.error(f"Error creating graphs section: {str(e)}")
            return []

    async def _create_symptoms_graph(
        self,
        symptoms: List[Dict],
        language: str
    ) -> Optional[BytesIO]:
        """Create symptoms severity graph"""
        try:
            # Extract data
            names = []
            values = []
            for symptom in symptoms:
                name = symptom['name']
                if not LanguageMetadata.should_preserve_medical_terms(language):
                    name = await self._translate_text(name, language)
                names.append(name)
                values.append(symptom.get('severity', 0))
            
            # Create graph
            plt.figure(figsize=(8, 6))
            plt.bar(names, values)
            plt.xlabel(await self._translate_text("Symptoms", language))
            plt.ylabel(await self._translate_text("Severity", language))
            
            # Save to buffer
            buffer = BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight')
            plt.close()
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error creating symptoms graph: {str(e)}")
            return None

    async def _translate_text(self, text: str, target_language: str) -> str:
        """Translate text with caching"""
        if target_language == "en":
            return text
            
        try:
            # Try cache first
            cache_key = f"translation:{text}:{target_language}"
            cached = self.template_cache.get(cache_key)
            if cached:
                return cached
            
            # Translate
            result = await self.bhashini_service.translate_text(
                text=text,
                source_language="en",
                target_language=target_language
            )
            
            # Cache result
            translated = result.get("text", text)
            self.template_cache[cache_key] = translated
            
            return translated
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            return text

    def _get_report_layout(self) -> Dict:
        """Get report layout configuration"""
        return {
            "margins": {
                "top": 72,
                "bottom": 72,
                "left": 72,
                "right": 72
            },
            "spacing": {
                "title": 20,
                "section": 15,
                "paragraph": 10
            }
        }
# backend/app/utils/response_validator.py
from typing import Dict, List, Optional, Tuple
import re
import logging
from datetime import datetime
from pydantic import BaseModel
from app.config.database import redis_client, translations_cache
from app.config.language_metadata import LanguageMetadata
import json
import asyncio

logger = logging.getLogger(__name__)

class ValidationResult(BaseModel):
    """Model for validation results"""
    is_valid: bool
    safety_concerns: List[str] = []
    missing_elements: List[str] = []
    emergency_level: str = "none"
    improvement_needed: bool = False
    confidence_scores: Dict[str, float] = {}
    suggested_improvements: List[str] = []
    metadata: Dict = {}

class AIResponseValidator:
    def __init__(self):
        # Keep existing translation cache
        self.translation_cache = translations_cache
        
        # Cache settings
        self.cache_duration = 3600  # 1 hour
        self.validation_patterns = self._load_validation_patterns()
        
        # Concurrent validation limit
        self.validation_semaphore = asyncio.Semaphore(10)
        
        # Emergency detection threshold
        self.emergency_threshold = 0.8
        
        # Initialize language-specific patterns
        self._initialize_language_patterns()

    def _initialize_language_patterns(self):
        """Initialize validation patterns for different languages"""
        self.language_patterns = {}
        
        for lang_code in LanguageMetadata.get_supported_languages():
            # Get language metadata
            lang_meta = LanguageMetadata.get_language_metadata(lang_code)
            
            # Store patterns specific to each language
            self.language_patterns[lang_code] = {
                'symptom_mention': self._get_language_patterns(lang_code, 'symptoms'),
                'confidence_score': r'\[(?:Confidence|विश्वास|விசுவாசம்):\s*(\d+)%\]',
                'emergency_keywords': self._get_language_patterns(lang_code, 'emergency'),
                'medical_terms': self._get_language_patterns(lang_code, 'medical')
            }

    def _get_language_patterns(self, language: str, pattern_type: str) -> str:
        """Get regex patterns for specific language and type"""
        base_patterns = {
            'symptoms': {
                'en': r'symptom|pain|discomfort|feeling|condition',
                'hi': r'लक्षण|दर्द|तकलीफ़|महसूस|स्थिति',
                # Add patterns for other languages
            },
            'emergency': {
                'en': r'emergency|immediate|urgent|serious|severe',
                'hi': r'आपातकालीन|तत्काल|गंभीर|जरूरी',
                # Add patterns for other languages
            },
            'medical': {
                'en': r'diagnosis|treatment|medication|prescription',
                'hi': r'निदान|इलाज|दवा|पर्चा',
                # Add patterns for other languages
            }
        }
        
        return base_patterns[pattern_type].get(language, base_patterns[pattern_type]['en'])

    def _load_validation_patterns(self) -> Dict:
        """Load and compile regex patterns"""
        return {
            'symptom_mention': re.compile(r'symptom|pain|discomfort|feeling|condition', re.IGNORECASE),
            'confidence_score': re.compile(r'\[Confidence:\s*(\d+)%\]'),
            'recommendation': re.compile(r'\[Recommendation:.*?\]'),
            'emergency_keywords': re.compile(r'emergency|immediate|urgent|serious|severe', re.IGNORECASE),
            # Preserve existing patterns
            'medical_terms': re.compile(r'\b(diagnosis|treatment|medication|prescription)\b', re.IGNORECASE)
        }

    async def validate_response(
        self,
        response: str,
        source_language: str = "en",
        target_language: Optional[str] = None,
        context: Optional[List[Dict]] = None
    ) -> Tuple[bool, str, ValidationResult]:
        """Validate and clean response with language support"""
        async with self.validation_semaphore:
            try:
                # Get language-specific patterns
                patterns = self.language_patterns.get(
                    source_language,
                    self.language_patterns['en']
                )
                
                # Extract confidence scores
                confidence_matches = list(re.finditer(
                    patterns['confidence_score'],
                    response
                ))
                confidence_scores = [
                    int(match.group(1)) for match in confidence_matches
                ]
                
                # Check for emergency keywords
                emergency_matches = re.findall(
                    patterns['emergency_keywords'],
                    response,
                    re.IGNORECASE
                )
                emergency_level = self._determine_emergency_level(
                    emergency_matches,
                    confidence_scores
                )
                
                # Extract medical terms
                medical_terms = re.findall(
                    patterns['medical_terms'],
                    response,
                    re.IGNORECASE
                )
                
                # Validate medical content
                medical_validation = await self._validate_medical_content(
                    response,
                    medical_terms,
                    source_language,
                    context
                )
                
                # Structure the validation result
                validation_result = ValidationResult(
                    is_valid=medical_validation['is_valid'],
                    safety_concerns=medical_validation['safety_concerns'],
                    missing_elements=medical_validation['missing_elements'],
                    emergency_level=emergency_level,
                    improvement_needed=medical_validation['needs_improvement'],
                    confidence_scores={
                        'overall': sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
                        'medical_terms': medical_validation['confidence'],
                        'language': medical_validation['language_confidence']
                    },
                    suggested_improvements=medical_validation['suggestions'],
                    metadata={
                        'language': {
                            'source': source_language,
                            'target': target_language,
                            'medical_terms_preserved': medical_validation['preserved_terms']
                        },
                        'validation_timestamp': datetime.utcnow().isoformat()
                    }
                )
                
                # Handle translations if needed
                if target_language and target_language != source_language:
                    processed_response = await self._handle_translation(
                        response,
                        source_language,
                        target_language,
                        medical_terms,
                        validation_result
                    )
                else:
                    processed_response = self._clean_response(response)
                
                return (
                    validation_result.is_valid,
                    "",
                    processed_response
                )

            except Exception as e:
                logger.error(f"Error validating response: {str(e)}")
                return False, str(e), {}

    async def _validate_medical_content(
        self,
        response: str,
        medical_terms: List[str],
        language: str,
        context: Optional[List[Dict]]
    ) -> Dict:
        """Validate medical content in response"""
        try:
            # Get language metadata
            lang_meta = LanguageMetadata.get_language_metadata(language)
            
            # Initialize validation result
            validation = {
                'is_valid': True,
                'safety_concerns': [],
                'missing_elements': [],
                'needs_improvement': False,
                'suggestions': [],
                'confidence': 0.0,
                'language_confidence': 0.0,
                'preserved_terms': []
            }
            
            # Check for required medical elements
            if medical_terms:
                # Validate medical term usage
                medical_validation = await self._validate_medical_terms(
                    medical_terms,
                    language,
                    context
                )
                validation.update(medical_validation)
                
                # Check if medical terms should be preserved
                if LanguageMetadata.should_preserve_medical_terms(language):
                    validation['preserved_terms'].extend(medical_terms)
            
            # Check for context consistency
            if context:
                context_validation = self._validate_context_consistency(
                    response,
                    context,
                    language
                )
                validation.update(context_validation)
            
            return validation
            
        except Exception as e:
            logger.error(f"Error validating medical content: {str(e)}")
            return {
                'is_valid': False,
                'safety_concerns': ["Validation error occurred"],
                'missing_elements': [],
                'needs_improvement': True,
                'suggestions': ["Review medical content"],
                'confidence': 0.0,
                'language_confidence': 0.0,
                'preserved_terms': []
            }

    async def _validate_medical_terms(
        self,
        terms: List[str],
        language: str,
        context: Optional[List[Dict]]
    ) -> Dict:
        """Validate medical terms usage"""
        # Existing medical term validation logic...
        pass

    def _validate_context_consistency(
        self,
        response: str,
        context: List[Dict],
        language: str
    ) -> Dict:
        """Validate response consistency with conversation context"""
        # Existing context validation logic...
        pass

    def _determine_emergency_level(
        self,
        emergency_matches: List[str],
        confidence_scores: List[int]
    ) -> str:
        """Determine emergency level of response"""
        if not emergency_matches:
            return "none"
            
        # Calculate emergency score
        emergency_score = len(emergency_matches) / 10  # Normalize
        
        # Factor in confidence scores
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            emergency_score *= (avg_confidence / 100)
        
        if emergency_score >= self.emergency_threshold:
            return "high"
        elif emergency_score >= self.emergency_threshold / 2:
            return "medium"
        return "low"

    async def _handle_translation(
        self,
        text: str,
        source_language: str,
        target_language: str,
        medical_terms: List[str],
        validation_result: ValidationResult
    ) -> str:
        """Handle translation while preserving medical terms"""
        try:
            # Check cache first
            cached_translation = await self._get_cached_translation(
                text,
                source_language,
                target_language
            )
            
            if cached_translation:
                return cached_translation
            
            # Preserve medical terms if needed
            preserved_terms = {}
            if validation_result.metadata['language']['medical_terms_preserved']:
                for term in medical_terms:
                    placeholder = f"__MEDICAL_TERM_{len(preserved_terms)}__"
                    preserved_terms[placeholder] = term
                    text = text.replace(term, placeholder)
            
            # Translate modified text
            translated_text = await self._translate_text(
                text,
                source_language,
                target_language
            )
            
            # Restore preserved terms
            for placeholder, term in preserved_terms.items():
                translated_text = translated_text.replace(placeholder, term)
            
            # Cache translation
            await self._cache_translation(
                text,
                translated_text,
                source_language,
                target_language
            )
            
            return translated_text
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            return text

    def _clean_response(self, response: str) -> str:
        """Clean response text"""
        # Remove confidence markers
        cleaned = re.sub(r'\[Confidence:.*?\]', '', response)
        # Remove recommendation markers
        cleaned = re.sub(r'\[Recommendation:.*?\]', '', cleaned)
        return cleaned.strip()

    async def enhance_response(
        self,
        response: Dict,
        language: str
    ) -> str:
        """Enhance response with proper formatting"""
        enhanced = response['main_response']
        
        # Get language metadata
        lang_meta = LanguageMetadata.get_language_metadata(language)
        
        # Add confidence context if scores are low
        if response['confidence_scores']['overall'] < 70:
            disclaimer = await self._get_localized_disclaimer(language)
            enhanced += f"\n\n{disclaimer}"
        
        # Add emergency warning if detected
        if response['emergency_level'] == "high":
            warning = await self._get_localized_emergency_warning(language)
            enhanced = f"{warning}\n\n{enhanced}"
        
        # Add recommendations
        if response['recommendations']:
            header = await self._get_localized_text('recommendations', language)
            enhanced += f"\n\n{header}:\n"
            enhanced += "\n".join(
                f"• {rec}" for rec in response['recommendations']
            )
        
        # Handle RTL if needed
        if lang_meta['rtl']:
            enhanced = self._format_rtl_text(enhanced)
        
        return enhanced

    async def _get_localized_text(
        self,
        key: str,
        language: str
    ) -> str:
        """Get localized text for given key"""
        # Implementation for getting localized text
        pass

    def _format_rtl_text(self, text: str) -> str:
        """Format text for RTL languages"""
        # Implementation for RTL formatting
        pass

    async def _translate_and_cache(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> str:
        """Translate text and cache the result."""
        try:
            # Translation would be handled by Bhashini service
            translated_text = text  # Replace with actual translation call

            # Cache the translation
            await self.translation_cache.cache_translation(
                text,
                translated_text,
                source_language,
                target_language
            )

            return translated_text
        except Exception as e:
            logger.error(f"Error in translation: {str(e)}")
            return text

    def enhance_response(self, response: Dict) -> str:
        """Enhance the response with proper formatting and additional context."""
        enhanced = response['main_response']

        # Add confidence context if scores are low
        if response['average_confidence'] < 70:
            enhanced += "\n\nPlease note: This assessment is based on limited information. A medical professional can provide a more accurate evaluation."

        # Add emergency warning if detected
        if response['requires_emergency']:
            enhanced = "⚠️ IMPORTANT: Based on your symptoms, immediate medical attention may be required.\n\n" + enhanced

        # Add recommendations
        if response['recommendations']:
            enhanced += "\n\nRecommendations:\n" + "\n".join(f"• {rec}" for rec in response['recommendations'])

        return enhanced
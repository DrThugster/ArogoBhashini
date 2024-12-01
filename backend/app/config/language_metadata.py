# backend/app/config/language_metadata.py
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class VoiceConfig:
    """Standard voice configuration for all languages"""
    AVAILABLE_GENDERS = ["male", "female"]
    DEFAULT_GENDER = "female"
    SUPPORTED_STYLES = ["neutral", "formal"]
    SAMPLING_RATE = 22050
    ENCODING = "LINEAR16"
    AUDIO_FORMAT = "wav"

class LanguageMetadata:
    """Centralized language metadata configuration"""
    
    # ISO 639 language codes mapping
    LANGUAGE_CODES = {
        "en": "English",
        "hi": "Hindi",
        "ta": "Tamil",
        "te": "Telugu",
        "kn": "Kannada",
        "ml": "Malayalam",
        "bn": "Bengali",
        "gu": "Gujarati",
        "mr": "Marathi",
        "pa": "Punjabi",
        "as": "Assamese",
        "bo": "Bodo",
        "mni": "Manipuri",
        "or": "Odia",
        "raj": "Rajasthani",
        "ur": "Urdu"
    }

    LANGUAGE_METADATA = {
        "en": {
            "name": "English",
            "script": "Latin",
            "rtl": False,
            "variants": ["eng", "en-IN", "en-US"],
            "detection_patterns": [
                "hello", "hi", "hey", "good morning",
                "thank you", "thanks", "yes", "no"
            ],
            "font_family": "Helvetica",
            "fallback_fonts": ["Arial", "Times New Roman"]
        },
        "hi": {
            "name": "Hindi",
            "script": "Devanagari",
            "rtl": False,
            "variants": ["hin", "hi-IN"],
            "detection_patterns": [
                "नमस्ते", "हाँ", "नहीं", "धन्यवाद",
                "सुप्रभात", "शुभ प्रभात", "ठीक है"
            ],
            "font_family": "Noto Sans Devanagari",
            "fallback_fonts": ["Mangal", "Arial Unicode MS"]
        }
    }


    # Term preservation settings
    PRESERVE_MEDICAL_TERMS = {
        "en": False,  # Default language
        "hi": True    # Preserve English medical terms in Hindi
    }


    @classmethod
    def get_language_name(cls, code: str) -> str:
        """Get language name from code"""
        return cls.LANGUAGE_CODES.get(code, "Unknown")

    @classmethod
    def get_language_metadata(cls, code: str) -> Dict:
        """Get complete metadata for a language"""
        return cls.LANGUAGE_METADATA.get(code, {})


    @classmethod
    def is_language_supported(cls, code: str) -> bool:
        """Check if a language is supported"""
        return code in cls.LANGUAGE_CODES

    @classmethod
    def get_supported_languages(cls) -> List[str]:
        """Get list of all supported language codes"""
        return list(cls.LANGUAGE_CODES.keys())
    
    @classmethod
    def get_language_variants(cls, code: str) -> List[str]:
        """Get language variants for detection"""
        return cls.LANGUAGE_METADATA.get(code, {}).get("variants", [])

    @classmethod
    def get_detection_patterns(cls, code: str) -> List[str]:
        """Get language detection patterns"""
        return cls.LANGUAGE_METADATA.get(code, {}).get("detection_patterns", [])

    @classmethod
    def get_font_config(cls, language: str) -> Dict:
        """Get font configuration for a language"""
        lang_meta = cls.LANGUAGE_METADATA.get(language, cls.LANGUAGE_METADATA["en"])
        return {
            "font_family": lang_meta["font_family"],
            "fallback_fonts": lang_meta["fallback_fonts"]
        }
    
    @classmethod
    def get_script_direction(cls, language: str) -> str:
        """Get script direction (LTR or RTL)"""
        return "rtl" if cls.LANGUAGE_METADATA.get(language, {}).get("rtl", False) else "ltr"

    @classmethod
    def should_preserve_medical_terms(cls, language: str) -> bool:
        """Check if medical terms should be preserved in English"""
        return cls.PRESERVE_MEDICAL_TERMS.get(language, False)
    
    @classmethod
    def get_voice_config(cls) -> Dict:
        """Get standard voice configuration"""
        return {
            "genders": VoiceConfig.AVAILABLE_GENDERS,
            "default_gender": VoiceConfig.DEFAULT_GENDER,
            "styles": VoiceConfig.SUPPORTED_STYLES,
            "sampling_rate": VoiceConfig.SAMPLING_RATE,
            "encoding": VoiceConfig.ENCODING,
            "format": VoiceConfig.AUDIO_FORMAT
        }
    
    @classmethod
    def validate_voice_options(
        cls,
        gender: str,
        style: Optional[str] = None
    ) -> tuple[str, Optional[str]]:
        """Validate and get default voice options if needed"""
        if gender not in VoiceConfig.AVAILABLE_GENDERS:
            gender = VoiceConfig.DEFAULT_GENDER
        
        if style and style not in VoiceConfig.SUPPORTED_STYLES:
            style = "neutral"
            
        return gender, style
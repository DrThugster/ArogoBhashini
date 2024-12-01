# backend/app/utils/symptom_analyzer.py
from typing import Dict, List, Optional
import logging
from app.utils.ai_config import GeminiConfig
import json
from transformers import pipeline
from app.config.language_metadata import LanguageMetadata
import asyncio
from functools import lru_cache
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import datetime
from typing import Set

logger = logging.getLogger(__name__)

class SymptomAnalyzer:
    def __init__(self):
        self.ai_config = GeminiConfig()
        
        # Initialize NER models with caching
        self._initialize_ner_models()
        
        # Thread pool for CPU-intensive operations
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        
        # Caching configurations
        self.cache_ttl = 3600  # 1 hour
        self.max_cache_size = 1000
        

    def _initialize_ner_models(self):
        """Initialize NER models with optimization"""
        try:
            # Primary medical NER model
            self.medical_ner = pipeline(
                "ner",
                model="samrawal/bert-base-uncased_clinical-ner",
                device=0 if self._cuda_available() else -1,
                batch_size=32
            )
            
            # Simplified model for quick checks
            self.quick_ner = pipeline(
                "ner",
                model="samrawal/bert-base-uncased_clinical-ner",
                device=0 if self._cuda_available() else -1,
                batch_size=32,
                aggregation_strategy="simple"
            )
            
            logger.info("NER models initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing NER models: {str(e)}")
            raise

    def _extract_conversation_text(self, chat_history: List[Dict]) -> str:
        """Extract text from conversation history"""
        conversation_text = []
        for message in chat_history:
            if "content" in message:
                conversation_text.append(message["content"])
            if "english_content" in message:
                conversation_text.append(message["english_content"])
        return " ".join(conversation_text)

    @lru_cache(maxsize=100)
    async def analyze_medical_content(self, text: str, language: str) -> Dict:
        """Analyze medical content using AI"""
        try:
            cache_key = f"{text}:{language}"
            
            # Check cache first
            cached_result = self._get_cached_analysis(cache_key)
            if cached_result:
                return cached_result

            # Prepare analysis prompt
            prompt = f"""
            Analyze the following medical text and identify:
            1. Medical terms and symptoms
            2. Severity indicators
            3. Emergency signals
            4. Treatment references
            
            Text: {text}
            
            Provide structured analysis with confidence scores.
            """

            # Get AI analysis
            response = await self.ai_config.model.generate_content(prompt)
            analysis = json.loads(response.text)  # Assuming structured JSON response
            
            # Quick validation using NER
            ner_entities = self.ner_pipeline(text)
            medical_entities = [
                entity for entity in ner_entities 
                if entity['entity'].startswith('B-PROBLEM')
            ]
            
            # Combine AI and NER results
            combined_analysis = {
                "terms": analysis.get("medical_terms", []),
                "symptoms": analysis.get("symptoms", []),
                "severity": analysis.get("severity", 0),
                "emergency_indicators": analysis.get("emergency_signals", []),
                "confidence": analysis.get("confidence", 0.0),
                "ner_validated": bool(medical_entities),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Cache the result
            self._cache_analysis(cache_key, combined_analysis)
            
            return combined_analysis

        except Exception as e:
            logger.error(f"Error analyzing medical content: {str(e)}")
            return {
                "terms": [],
                "symptoms": [],
                "severity": 0,
                "emergency_indicators": [],
                "confidence": 0.0,
                "error": str(e)
            }

    def _get_cached_analysis(self, key: str) -> Optional[Dict]:
        """Get cached analysis if valid"""
        if key in self.analysis_cache:
            cached = self.analysis_cache[key]
            cache_time = datetime.fromisoformat(cached["timestamp"])
            
            if datetime.utcnow() - cache_time < self.cache_ttl:
                return cached
            
            # Remove expired cache
            del self.analysis_cache[key]
        return None

    def _cache_analysis(self, key: str, analysis: Dict):
        """Cache analysis result"""
        self.analysis_cache[key] = analysis
        
        # Clean old cache entries
        current_time = datetime.utcnow()
        expired_keys = [
            k for k, v in self.analysis_cache.items()
            if current_time - datetime.fromisoformat(v["timestamp"]) >= self.cache_ttl
        ]
        
        for k in expired_keys:
            del self.analysis_cache[k]

    async def analyze_conversation(
        self,
        chat_history: List[Dict],
        language: str = "en"
    ) -> Dict:
        """Analyze conversation with optimized processing"""
        try:
            # Extract relevant text
            conversation_text = self._extract_conversation_text(chat_history)
            
            # Process in parallel
            async with asyncio.TaskGroup() as group:
                # NER analysis
                ner_task = group.create_task(
                    self._process_ner(conversation_text)
                )
                
                # Medical term extraction
                terms_task = group.create_task(
                    self._extract_medical_terms(conversation_text, language)
                )
                
                # Symptom severity analysis
                severity_task = group.create_task(
                    self._analyze_severity(conversation_text)
                )
            
            # Combine results
            analysis = {
                "symptoms": ner_task.result(),
                "medical_terms": terms_task.result(),
                "severity": severity_task.result(),
                "emergency_level": self._determine_emergency_level(
                    ner_task.result(),
                    severity_task.result()
                )
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing conversation: {str(e)}")
            return self._get_fallback_analysis()

    async def _process_ner(self, text: str) -> List[Dict]:
        """Process NER with optimization"""
        try:
            # Run NER in thread pool
            loop = asyncio.get_event_loop()
            entities = await loop.run_in_executor(
                self.thread_pool,
                self._run_ner,
                text
            )
            
            # Process entities
            return self._process_entities(entities)
            
        except Exception as e:
            logger.error(f"NER processing error: {str(e)}")
            return []

    def _run_ner(self, text: str) -> List[Dict]:
        """Run NER model with batching"""
        # Split text into manageable chunks
        chunks = self._split_text(text, max_length=512)
        
        # Process chunks
        all_entities = []
        for chunk in chunks:
            entities = self.medical_ner(chunk)
            all_entities.extend(entities)
        
        return all_entities

    def _process_entities(self, entities: List[Dict]) -> List[Dict]:
        """Process and deduplicate entities"""
        processed = {}
        for entity in entities:
            if entity["entity"].startswith("B-PROBLEM"):
                key = entity["word"].lower()
                if key not in processed:
                    processed[key] = {
                        "term": entity["word"],
                        "confidence": entity["score"],
                        "count": 1
                    }
                else:
                    processed[key]["count"] += 1
                    processed[key]["confidence"] = max(
                        processed[key]["confidence"],
                        entity["score"]
                    )
        
        return list(processed.values())

    @lru_cache(maxsize=1000)
    def _split_text(self, text: str, max_length: int = 512) -> List[str]:
        """Split text into optimal chunks"""
        # Implement smart text splitting
        return []  # Placeholder

    async def _extract_medical_terms(
        self,
        text: str,
        language: str
    ) -> List[str]:
        """Extract medical terms using AI and NER"""
        try:
            # Strategy 1: NER Model Analysis
            ner_entities = await self._process_ner(text)
            medical_entities = [
                entity["term"] for entity in ner_entities
                if entity["confidence"] > 0.7
            ]

            # Strategy 2: Gemini Medical Analysis
            prompt = f"""
            Analyze this text and identify medical terms, symptoms, and conditions.
            Focus on clinical terminology and patient symptoms.
            Text: {text}
            Return only the identified terms as a JSON array.
            Return empty array if no medical terms found.
            """
            response = self.ai_config.model.generate_content(prompt)
            ai_terms = json.loads(response.text if hasattr(response, 'text') else '[]')

            # Combine and deduplicate terms
            all_terms = set(medical_entities + ai_terms)
            
            # Validate terms through medical context if terms exist
            if all_terms:
                validated_terms = self._validate_medical_relevance(all_terms)
                return list(validated_terms)
            
            return list(all_terms)

        except Exception as e:
            logger.debug(f"Medical term extraction note: {str(e)}")
            return []

    def _validate_medical_relevance(self, terms: Set[str]) -> Set[str]:
        """Validate medical relevance of terms using Gemini"""
        try:
            prompt = f"""
            For each term, determine if it is a valid medical term, symptom, or condition.
            Terms: {list(terms)}
            Return only the valid medical terms as a JSON array.
            """
            response = self.ai_config.model.generate_content(prompt)
            return set(json.loads(response.text if hasattr(response, 'text') else '[]'))
        except:
            return terms


    async def _analyze_severity(self, text: str) -> Dict:
        """Analyze symptom severity using AI"""
        try:
            prompt = f"""
            Analyze these symptoms for severity. Return a JSON object with these exact fields:
            {{
                "severity_score": (1-10),
                "urgency_level": "low/medium/high",
                "key_risk_factors": [],
                "time_sensitivity": "routine/urgent/emergency"
            }}

            Text: {text}
            """

            # Generate and parse response
            response = self.ai_config.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Handle potential JSON formatting
            if not response_text.startswith('{'):
                response_text = response_text.split('```json')[-1].split('```')[0]
            
            severity_analysis = json.loads(response_text)

            # Enhance with NER validation
            ner_entities = await self._process_ner(text)
            critical_symptoms = [
                entity for entity in ner_entities 
                if entity["confidence"] > 0.8
            ]

            return {
                "severity_score": int(severity_analysis.get("severity_score", 1)),
                "urgency_level": severity_analysis.get("urgency_level", "low"),
                "risk_factors": severity_analysis.get("key_risk_factors", []),
                "time_sensitivity": severity_analysis.get("time_sensitivity", "routine"),
                "critical_symptoms": [symptom["term"] for symptom in critical_symptoms],
                "confidence": sum(entity["confidence"] for entity in critical_symptoms) / len(critical_symptoms) if critical_symptoms else 0.5,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

        except json.JSONDecodeError:
            logger.debug("Retrying with cleaned response format")
            return self._get_default_severity()
        except Exception as e:
            logger.error(f"Severity analysis error: {str(e)}")
            return self._get_default_severity()

    def _get_default_severity(self) -> Dict:
        """Return default severity analysis"""
        return {
            "severity_score": 1,
            "urgency_level": "low",
            "risk_factors": [],
            "time_sensitivity": "routine",
            "critical_symptoms": [],
            "confidence": 0.5,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }

    def _determine_emergency_level(
        self,
        symptoms: List[Dict],
        severity: Dict
    ) -> str:
        """Determine emergency level"""
        # Implement emergency level detection
        return "low"  # Placeholder

    def _get_fallback_analysis(self) -> Dict:
        """Get fallback analysis for errors"""
        return {
            "symptoms": [],
            "medical_terms": [],
            "severity": {"level": "unknown", "confidence": 0.0},
            "emergency_level": "unknown"
        }

    def _cuda_available(self) -> bool:
        """Check CUDA availability"""
        try:
            import torch
            return torch.cuda.is_available()
        except:
            return False

    async def cleanup(self):
        """Cleanup resources"""
        self.thread_pool.shutdown()
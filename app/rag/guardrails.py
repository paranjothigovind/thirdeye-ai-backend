"""Guardrails for safe responses"""
from typing import Dict, Any, List
import re

from app.core.logging import get_logger

logger = get_logger(__name__)


class Guardrails:
    """Safety guardrails for meditation guidance"""
    
    # Medical/diagnostic keywords to flag
    MEDICAL_KEYWORDS = [
        "diagnose", "diagnosis", "cure", "treat", "treatment",
        "prescribe", "prescription", "medication", "drug",
        "disease", "disorder", "condition", "illness"
    ]
    
    # Required disclaimers
    DISCLAIMERS = {
        "medical": "⚠️ This is not medical advice. Consult a healthcare professional for medical concerns.",
        "spiritual": "🙏 This guidance is based on traditional teachings. Individual experiences may vary.",
        "safety": "⚠️ If you experience discomfort, dizziness, or distress, stop the practice and seek guidance."
    }
    
    def check_query(self, query: str) -> Dict[str, Any]:
        """Check if query is appropriate"""
        query_lower = query.lower()
        
        issues = []
        
        # Check for medical queries
        if any(keyword in query_lower for keyword in self.MEDICAL_KEYWORDS):
            issues.append("medical_query")
        
        # Check for emergency keywords
        emergency_keywords = ["emergency", "crisis", "suicide", "harm"]
        if any(keyword in query_lower for keyword in emergency_keywords):
            issues.append("emergency")
        
        return {
            "is_safe": len(issues) == 0,
            "issues": issues,
            "requires_disclaimer": len(issues) > 0
        }
    
    def check_response(self, response: str) -> Dict[str, Any]:
        """Check if response is safe and appropriate"""
        response_lower = response.lower()
        
        issues = []
        suggestions = []
        
        # Check for medical advice
        if any(keyword in response_lower for keyword in self.MEDICAL_KEYWORDS):
            issues.append("contains_medical_advice")
            suggestions.append("Remove medical advice and add disclaimer")
        
        # Check for citations
        if "[source:" not in response_lower:
            issues.append("missing_citations")
            suggestions.append("Add source citations")
        
        # Check for safety warnings (when discussing practices)
        practice_keywords = ["practice", "technique", "exercise", "meditation"]
        has_practice = any(keyword in response_lower for keyword in practice_keywords)
        has_warning = any(word in response_lower for word in ["caution", "warning", "risk", "contraindication"])
        
        if has_practice and not has_warning:
            issues.append("missing_safety_warning")
            suggestions.append("Add safety warnings or contraindications")
        
        return {
            "is_safe": len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions
        }
    
    def add_disclaimers(self, response: str, disclaimer_types: List[str]) -> str:
        """Add appropriate disclaimers to response"""
        disclaimers = []
        
        for dtype in disclaimer_types:
            if dtype in self.DISCLAIMERS:
                disclaimers.append(self.DISCLAIMERS[dtype])
        
        if disclaimers:
            disclaimer_text = "\n\n" + "\n".join(disclaimers)
            return response + disclaimer_text
        
        return response
    
    def handle_emergency(self) -> str:
        """Return emergency response"""
        return """🚨 If you're experiencing a mental health emergency or crisis, please:

1. Call emergency services (911 in US)
2. Contact a crisis helpline:
   - National Suicide Prevention Lifeline: 988
   - Crisis Text Line: Text HOME to 741741
3. Go to your nearest emergency room

This chatbot provides meditation guidance only and cannot help with emergencies. Please seek immediate professional help."""


# Global guardrails instance
guardrails = Guardrails()
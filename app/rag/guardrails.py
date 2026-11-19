"""Guardrails for safe responses"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _word_pattern(terms: List[str]) -> re.Pattern:
    """Whole-word, case-insensitive match for ASCII terms (inflections listed explicitly)."""
    return re.compile(r"\b(?:" + "|".join(terms) + r")\b", re.IGNORECASE)


DEFAULT_EMERGENCY_MESSAGE = (
    "🚨 If you are in immediate danger, or thinking about harming yourself, please contact "
    "your local emergency services right now, or reach out immediately to someone you trust "
    "who can be with you.\n\n"
    "This assistant offers meditation guidance only and cannot help in an emergency. "
    "Please seek immediate help from a qualified professional."
)


class EmergencyPolicy:
    """Region-specific emergency guidance loaded from ``EMERGENCY_POLICY_FILE``.

    Contacts are used only when the file records who approved them and when;
    extra keywords (e.g. Tamil) only when the file records who reviewed them.
    Otherwise the generic message (no phone numbers) is used.
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        data = data or {}
        self.region: str = str(data.get("region") or "")
        self.contacts: List[Dict[str, str]] = []
        self.keywords: List[str] = []
        self.message: str = DEFAULT_EMERGENCY_MESSAGE

        approval = data.get("contacts_approval") or {}
        contacts = data.get("contacts") or []
        if contacts and approval.get("approved_by") and approval.get("approved_on"):
            self.contacts = [
                {"name": str(c.get("name", "")).strip(), "value": str(c.get("value", "")).strip()}
                for c in contacts
                if str(c.get("name", "")).strip() and str(c.get("value", "")).strip()
            ]
        elif contacts:
            logger.warning("Emergency policy contacts ignored: missing contacts_approval.approved_by/approved_on")

        keyword_block = data.get("keywords") or {}
        terms = [str(t).strip() for t in keyword_block.get("terms") or [] if str(t).strip()]
        if terms and keyword_block.get("reviewed_by"):
            self.keywords = terms
        elif terms:
            logger.warning("Emergency policy keywords ignored: missing keywords.reviewed_by")

    @classmethod
    def from_file(cls, path: str) -> "EmergencyPolicy":
        if not path:
            return cls()
        try:
            return cls(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            logger.error(f"Could not load EMERGENCY_POLICY_FILE ({type(error).__name__}); using generic guidance")
            return cls()

    def render(self) -> str:
        if not self.contacts:
            return self.message
        lines = "\n".join(f"- {c['name']}: {c['value']}" for c in self.contacts)
        return f"{self.message}\n\nEmergency contacts:\n{lines}"


class Guardrails:
    """Safety guardrails for meditation guidance"""

    # Medical/diagnostic keywords to flag
    MEDICAL_KEYWORDS = [
        "diagnose", "diagnosis", "cure", "treat", "treatment",
        "prescribe", "prescription", "medication", "drug",
        "disease", "disorder", "condition", "illness"
    ]
    # Whole-word forms of MEDICAL_KEYWORDS (avoids e.g. "unconditional", "treaty")
    MEDICAL_PATTERN = _word_pattern([
        r"diagnos(?:e|es|ed|ing|is)", r"cur(?:e|es|ed|ing)", r"treat(?:s|ed|ing)?",
        r"treatments?", r"prescri(?:be|bes|bed|bing)", r"prescriptions?",
        r"medications?", r"drugs?", r"diseases?", r"disorders?", r"conditions?",
        r"illness(?:es)?",
    ])

    EMERGENCY_KEYWORDS = ["emergency", "crisis", "suicide", "harm"]
    # Whole-word forms of EMERGENCY_KEYWORDS plus explicit crisis phrases
    # (avoids e.g. "harmony", "pharmacy")
    EMERGENCY_PATTERN = _word_pattern([
        r"emergenc(?:y|ies)", r"cris(?:is|es)", r"suicid(?:e|es|al)",
        r"harm(?:s|ed|ing|ful)?", r"self[- ]?harm(?:ing)?",
        r"kill(?:ing)? myself", r"end(?:ing)? my life", r"hurt(?:ing)? myself",
        r"want to die", r"(?:do not|don['’]t|dont|no longer) want to (?:live|be alive|exist)",
        r"end(?:ing)? it all", r"not worth living", r"better off dead",
    ])

    # Required disclaimers
    DISCLAIMERS = {
        "medical": "⚠️ This is not medical advice. Consult a healthcare professional for medical concerns.",
        "spiritual": "🙏 This guidance is based on traditional teachings. Individual experiences may vary.",
        "safety": "⚠️ If you experience discomfort, dizziness, or distress, stop the practice and seek guidance."
    }

    def __init__(self, policy: Optional[EmergencyPolicy] = None):
        self.policy = policy or EmergencyPolicy.from_file(settings.EMERGENCY_POLICY_FILE)

    def _is_emergency(self, text: str) -> bool:
        if self.EMERGENCY_PATTERN.search(text):
            return True
        lowered = text.casefold()
        # Reviewed policy keywords: substring match (works for Tamil, where
        # suffixes attach to words and \b is unreliable)
        return any(term.casefold() in lowered for term in self.policy.keywords)

    def check_query(self, query: str) -> Dict[str, Any]:
        """Check if query is appropriate"""
        issues = []

        # Check for medical queries
        if self.MEDICAL_PATTERN.search(query):
            issues.append("medical_query")

        # Check for emergency keywords
        if self._is_emergency(query):
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
        if self.MEDICAL_PATTERN.search(response):
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
        """Return the emergency response for the configured region policy"""
        return self.policy.render()


# Global guardrails instance
guardrails = Guardrails()

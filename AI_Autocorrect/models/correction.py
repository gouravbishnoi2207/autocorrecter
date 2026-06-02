from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CorrectionRecord:
    original_text: str
    corrected_text: str
    language: str
    id: int | None = None
    user_id: int | None = None
    analysis_mode: str = "transformer+rules"
    transformer_model: str = "prithivida/grammar_error_correcter_v1"
    context_before: str = ""
    corrections: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    explanations: List[Dict[str, Any]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    readability_score: float = 0.0
    sentiment_label: str = "Neutral"
    confidence_score: float = 0.0
    created_at: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "original_text": self.original_text,
            "corrected_text": self.corrected_text,
            "language": self.language,
            "analysis_mode": self.analysis_mode,
            "transformer_model": self.transformer_model,
            "context_before": self.context_before,
            "corrections": self.corrections,
            "stats": self.stats,
            "explanations": self.explanations,
            "keywords": self.keywords,
            "readability_score": self.readability_score,
            "sentiment_label": self.sentiment_label,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at,
        }

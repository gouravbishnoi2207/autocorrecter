import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List

from textblob import TextBlob


DEFAULT_TRANSFORMER_MODEL = "prithivida/grammar_error_correcter_v1"


@dataclass
class TransformerCorrectionResult:
    corrected_text: str
    confidence_score: float
    model_name: str
    used_transformer: bool
    explanation: str
    context_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corrected_text": self.corrected_text,
            "confidence_score": self.confidence_score,
            "model_name": self.model_name,
            "used_transformer": self.used_transformer,
            "explanation": self.explanation,
            "context_summary": self.context_summary,
        }


class ContextAwareTransformerCorrector:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or DEFAULT_TRANSFORMER_MODEL
        self._pipeline = None
        self._load_error: Exception | None = None

    def correct(self, text: str, context_before: str = "", language: str = "en") -> TransformerCorrectionResult:
        sentences = self._split_sentences(text)
        context_window = self._build_context(context_before)
        corrected_sentences: List[str] = []
        used_transformer = self._ensure_pipeline() is not None

        for index, sentence in enumerate(sentences):
            sentence_context = " ".join(context_window[-2:]) if context_window else ""
            if used_transformer:
                corrected_sentence = self._transform_sentence(sentence, sentence_context, language)
            else:
                corrected_sentence = self._fallback_sentence(sentence)

            corrected_sentences.append(self._normalize_sentence(corrected_sentence))
            context_window.append(corrected_sentences[-1])

        corrected_text = self._join_sentences(corrected_sentences)
        confidence_score = self._estimate_confidence(text, corrected_text, used_transformer)
        explanation = "Transformer-based correction was applied with sentence context." if used_transformer else "Transformer model unavailable; local grammar fallback was used."

        return TransformerCorrectionResult(
            corrected_text=corrected_text,
            confidence_score=confidence_score,
            model_name=self.model_name,
            used_transformer=used_transformer,
            explanation=explanation,
            context_summary=" | ".join(context_window[-3:]),
        )

    def _ensure_pipeline(self):
        if self._pipeline is not None or self._load_error is not None:
            return self._pipeline

        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                task="text2text-generation",
                model=self.model_name,
                tokenizer=self.model_name,
            )
        except Exception as exc:  # pragma: no cover - optional dependency path
            self._load_error = exc
            self._pipeline = None

        return self._pipeline

    def _transform_sentence(self, sentence: str, context: str, language: str) -> str:
        prompt_parts = [
            "Correct grammar, punctuation, and spelling while preserving meaning.",
            f"Language: {language}",
        ]
        if context:
            prompt_parts.append(f"Context: {context}")
        prompt_parts.append(f"Text: {sentence}")
        prompt = "\n".join(prompt_parts)

        output = self._pipeline(prompt, max_new_tokens=96, num_beams=4, do_sample=False)
        if not output:
            return sentence

        generated_text = output[0].get("generated_text") or output[0].get("summary_text") or sentence
        return generated_text.strip()

    def _fallback_sentence(self, sentence: str) -> str:
        corrected = str(TextBlob(sentence).correct())
        return corrected

    def _estimate_confidence(self, original_text: str, corrected_text: str, used_transformer: bool) -> float:
        if not original_text.strip():
            return 100.0

        similarity = self._sequence_similarity(original_text, corrected_text)
        base_score = 72.0 if used_transformer else 58.0
        return round(min(99.0, max(base_score, similarity * 100)), 2)

    def _sequence_similarity(self, original: str, corrected: str) -> float:
        from difflib import SequenceMatcher

        return SequenceMatcher(a=original.lower(), b=corrected.lower()).ratio()

    def _build_context(self, context_before: str) -> List[str]:
        return [segment for segment in self._split_sentences(context_before) if segment]

    def _split_sentences(self, text: str) -> List[str]:
        if not text.strip():
            return []

        pieces = re.split(r"(?<=[.!?])\s+", text.strip())
        return [piece.strip() for piece in pieces if piece.strip()]

    def _normalize_sentence(self, sentence: str) -> str:
        sentence = re.sub(r"\s+", " ", sentence.strip())
        if not sentence:
            return sentence
        if sentence[-1] not in ".!?":
            sentence += "."
        return sentence[:1].upper() + sentence[1:]

    def _join_sentences(self, sentences: List[str]) -> str:
        return " ".join(sentence for sentence in sentences if sentence).strip()


@lru_cache(maxsize=1)
def get_transformer_corrector() -> ContextAwareTransformerCorrector:
    return ContextAwareTransformerCorrector()
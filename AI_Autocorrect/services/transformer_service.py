import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict

from anthropic import Anthropic

DEFAULT_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are a precise proofreading engine. Correct spelling, grammar, and \
punctuation in the user's text while preserving their meaning, tone, and any technical \
terms, brand names, acronyms, or proper nouns (e.g. SaaS, API, admin, analytics) exactly \
as written unless they are genuinely misspelled. Do not rewrite for style. Do not change \
correct words. If the text is already correct, return it unchanged.

Respond with ONLY a JSON object, no markdown fences, no preamble:
{
  "corrected_text": "...",
  "changes": [
    {"original": "word/phrase", "corrected": "word/phrase", "reason": "short reason"}
  ]
}"""


@dataclass
class TransformerCorrectionResult:
    corrected_text: str
    confidence_score: float
    model_name: str
    used_transformer: bool
    explanation: str
    context_summary: str
    changes: list

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


class ClaudeCorrector:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or DEFAULT_MODEL
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._client = Anthropic(api_key=api_key) if api_key else None

    def correct(self, text: str, context_before: str = "", language: str = "en") -> TransformerCorrectionResult:
        if not text.strip():
            return TransformerCorrectionResult("", 100.0, self.model_name, False, "Empty input.", "", [])

        if self._client is None:
            return TransformerCorrectionResult(
                text, 50.0, self.model_name, False,
                "ANTHROPIC_API_KEY not set; correction skipped.", "", [],
            )

        user_message = f"Language: {language}\n"
        if context_before.strip():
            user_message += f"Preceding context: {context_before}\n"
        user_message += f"Text to correct:\n{text}"

        try:
            response = self._client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)

            corrected_text = parsed.get("corrected_text", text)
            changes = parsed.get("changes", [])
            confidence = 95.0 if changes else 99.0

            return TransformerCorrectionResult(
                corrected_text=corrected_text,
                confidence_score=confidence,
                model_name=self.model_name,
                used_transformer=True,
                explanation="Corrected using Claude with full-sentence context.",
                context_summary=context_before,
                changes=changes,
            )
          except Exception as exc:
            print(f"CLAUDE API ERROR: {type(exc).__name__}: {exc}", flush=True)

            return TransformerCorrectionResult(
                text,
                50.0,
                self.model_name,
                False,
                f"Claude correction failed: {exc}",
                "",
                [],
            )


@lru_cache(maxsize=1)
def get_transformer_corrector() -> ClaudeCorrector:
    return ClaudeCorrector()

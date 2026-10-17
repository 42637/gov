import json
import logging
import re
import time

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-3.8-flash"]


class GeminiService:
    def __init__(self, api_key: str | None, model: str):
        self.client = genai.Client(api_key=api_key) if api_key else None
        self.model = model

    def _json(self, prompt: str) -> dict:
        if not self.client:
            raise RuntimeError("Gemini API key is not configured")

        # Models to try: configured model first, followed by fallbacks
        models_to_try = [self.model]
        for m in FALLBACK_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = None
        for model_name in models_to_try:
            for attempt in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0,
                        ),
                    )

                    if not response or not response.text:
                        raise RuntimeError("Gemini returned an empty response")

                    raw_text = response.text.strip()
                    # Strip markdown code blocks if wrapped
                    if raw_text.startswith("```"):
                        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                        raw_text = re.sub(r"\s*```$", "", raw_text)

                    return json.loads(raw_text)

                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Gemini model %s attempt %d failed: %s", model_name, attempt + 1, exc
                    )
                    time.sleep(1.0)

        logger.error("All Gemini attempts failed. Last error: %s", last_error)
        raise RuntimeError(f"Gemini API call failed: {last_error}") from last_error

    def classify(self, question: str, context: str) -> dict:
        return self._json(
            f"""Classify this question for an Indian Government Schemes assistant. Return JSON only with boolean is_scheme_related, boolean evidence_sufficient, and concise reason. A question about Indian central/state schemes, benefits, eligibility, documents, applications, subsidies, scholarships, pensions or status is related. Evidence is sufficient only if the supplied evidence directly helps answer it.
Question: {question}
Evidence:
{context}"""
        )

    def answer(self, question: str, context: str) -> dict:
        return self._json(
            f"""Answer only from the supplied Indian Government Schemes evidence. Return JSON only: {{"summary":"...","sections":[{{"heading":"...","content":"..."}}]}}. Do not invent facts, amounts, eligibility, deadlines, documents, or links. Say a detail is unavailable when absent.
Question: {question}
Evidence:
{context}"""
        )

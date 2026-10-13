from __future__ import annotations

import json
import re
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationError

from app.db.models.question import Question
from app.services.ai.llm import LLMService


RUBRIC_SYSTEM_PROMPT = """
You are the Rubric Generator Agent for a university faculty-assistance system.
Create a teacher-reviewable marking rubric for ONE exam question.

NON-NEGOTIABLE RULES:
- Exactly 65% of the question's marks must belong to THEORY factors.
- Exactly 35% must belong to NON_THEORY factors.
- THEORY evaluates correctness, concepts, reasoning, derivation, definitions, or required technical content.
- NON_THEORY may evaluate relevance, completeness/coverage, clarity, structure, or notation where appropriate.
- Do not reward handwriting aesthetics or subjective personal style.
- Factors must be observable and usable by another examiner.
- Do not invent requirements that are not supported by the question/reference answer.
- Return JSON only.
""".strip()


class RubricFactorDraft(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=5)
    category: str
    weight_percent: Decimal = Field(gt=0, le=100)
    is_required: bool = True


class RubricDraft(BaseModel):
    factors: list[RubricFactorDraft] = Field(min_length=2)


class RubricGenerationError(RuntimeError):
    """Raised when the model returns an unusable rubric."""


class RubricGeneratorAgent:
    def __init__(self, llm: LLMService | None = None) -> None:
        self.llm = llm or LLMService()

    def generate(
        self,
        *,
        question: Question,
        reference_answer: str | None = None,
        teacher_notes: str | None = None,
    ) -> RubricDraft:
        prompt = f"""Generate a marking rubric for this question.

Question number: {question.question_no}
Maximum marks: {question.max_marks}
Question type: {question.question_type.value if question.question_type else "unknown"}
Section: {question.section or "unknown"}

QUESTION:
{question.question_text}

REFERENCE ANSWER (if available):
{reference_answer or "Not available"}

TEACHER NOTES:
{teacher_notes or "None"}

Use 3-6 factors total. Weights are percentages of the FULL question:
- theory factors together = exactly 65
- non_theory factors together = exactly 35

Return exactly:
{{"factors":[{{"name":"...", "description":"...", "category":"theory|non_theory", "weight_percent":0, "is_required":true}}]}}
"""
        response = self.llm.chat(
            system_prompt=RUBRIC_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.05,
            max_tokens=1200,
        )
        try:
            payload = self._parse_json(response.content)
            draft = RubricDraft.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise RubricGenerationError("The LLM returned an invalid rubric structure") from exc
        self.validate_weights(draft)
        return draft

    @staticmethod
    def validate_weights(draft: RubricDraft) -> None:
        theory = sum(
            (f.weight_percent for f in draft.factors if f.category == "theory"),
            Decimal("0"),
        )
        non_theory = sum(
            (f.weight_percent for f in draft.factors if f.category == "non_theory"),
            Decimal("0"),
        )
        if theory != Decimal("65"):
            raise RubricGenerationError(f"Theory factors must total 65%, got {theory}%")
        if non_theory != Decimal("35"):
            raise RubricGenerationError(
                f"Non-theory factors must total 35%, got {non_theory}%"
            )
        for factor in draft.factors:
            if factor.category not in {"theory", "non_theory"}:
                raise RubricGenerationError("Invalid marking factor category")

    @staticmethod
    def _parse_json(content: str) -> dict:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)

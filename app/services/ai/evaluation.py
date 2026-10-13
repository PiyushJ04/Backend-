from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.services.ai.llm import LLMService


# ============================================================
# Pydantic models
# ============================================================


class GeneratedFactorScore(BaseModel):
    factor_name: str
    ratio: Decimal = Field(ge=0, le=1)
    feedback: str = Field(default="", max_length=2000)

    @field_validator("ratio", mode="before")
    @classmethod
    def normalize_ratio(cls, value):
        if value is None:
            raise ValueError("ratio cannot be null")

        try:
            v = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid ratio value: {value!r}"
            ) from exc

        # Accept both:
        #   0.75 -> 0.75
        #   75   -> 0.75
        return v / Decimal("100") if v > 1 else v

class GeneratedEvaluationPoint(BaseModel):
    point: str = Field(min_length=1, max_length=1000)
    description: str | None = None
    weight: Decimal = Field(default=Decimal("0"), ge=0)
    score: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_point(cls, value):
        if isinstance(value, str):
            return {
                "point": value,
                "description": None,
                "weight": Decimal("0"),
                "score": Decimal("0"),
            }

        if isinstance(value, dict):
            value = dict(value)

            value.setdefault("description", None)
            value.setdefault("weight", Decimal("0"))
            value.setdefault("score", Decimal("0"))

            return value

        return value

    @field_validator("weight", "score", mode="before")
    @classmethod
    def normalize_number(cls, value):
        if value is None:
            return Decimal("0")

        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid numeric value: {value!r}"
            ) from exc

class GeneratedEvaluation(BaseModel):
    baseline_ratio: Decimal = Field(ge=0, le=1)

    academic_feedback: str = Field(
        default="",
        max_length=5000,
    )

    matched_points: list[GeneratedEvaluationPoint] = Field(
        default_factory=list,
        max_length=30,
    )

    missing_points: list[GeneratedEvaluationPoint] = Field(
        default_factory=list,
        max_length=30,
    )

    factor_scores: list[GeneratedFactorScore] = Field(
        default_factory=list,
        max_length=20,
    )

    @field_validator("baseline_ratio", mode="before")
    @classmethod
    def normalize_baseline(cls, value):
        if value is None:
            raise ValueError(
                "baseline_ratio cannot be null"
            )

        try:
            v = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid baseline_ratio value: {value!r}"
            ) from exc

        return v / Decimal("100") if v > 1 else v

class EvaluationGenerationError(RuntimeError):
    pass


# ============================================================
# System prompt
# ============================================================


SYSTEM_PROMPT = """You are an exam answer evaluation assistant operating under a teacher-approved marking scheme.

Evaluate ONLY the supplied student answer against:

1. The supplied approved baseline/reference answer.
2. The supplied key concepts.
3. The supplied expected points.
4. The supplied teacher-approved additional factors.

MARKING RULES:

- Academic correctness is exactly 75% of the question's marks.
- Additional approved factors are exactly 25%.
- Do not change these weights.
- Do not award points for factors that were not supplied.
- Do not invent facts that are absent from the student answer.
- Do not assume that a student demonstrated a point unless the answer provides evidence for it.
- For baseline_ratio, return a number from 0 to 1 representing the fraction of the academic 75% earned.
- For each supplied factor, return a ratio from 0 to 1 representing the fraction of that factor's allocated weight earned.
- Use matched_points for important baseline/reference points actually demonstrated.
- Use missing_points for important baseline/reference points not demonstrated.
- Keep feedback concise and evidence-based.

STRICT OUTPUT REQUIREMENT:

Return ONLY one valid JSON object.

Do NOT include markdown.
Do NOT include ```json.
Do NOT include explanations before or after the JSON.
Do NOT include trailing commas.

The JSON must have exactly this general structure:

{
  "baseline_ratio": 0.0,
  "academic_feedback": "...",
  "matched_points": [],
  "missing_points": [],
  "factor_scores": [
    {
      "factor_name": "...",
      "ratio": 0.0,
      "feedback": "..."
    }
  ]
}
"""


# ============================================================
# JSON extraction helper
# ============================================================


def _extract_json_object(content: str) -> str:
    """
    Extract the first complete JSON object from an LLM response.

    Handles responses such as:

        ```json
        {...}
        ```

    and:

        Here is the evaluation:
        {...}

    while rejecting responses that do not contain
    a complete JSON object.
    """

    cleaned = content.strip()

    # --------------------------------------------------------
    # Remove opening markdown code fence
    # --------------------------------------------------------

    cleaned = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Remove closing markdown code fence
    # --------------------------------------------------------

    cleaned = re.sub(
        r"\s*```\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = cleaned.strip()

    # --------------------------------------------------------
    # Fast path:
    # Entire response is already a JSON object.
    # --------------------------------------------------------

    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    # --------------------------------------------------------
    # Find the beginning of the first JSON object.
    # --------------------------------------------------------

    start = cleaned.find("{")

    if start == -1:
        raise EvaluationGenerationError(
            "LLM response did not contain a JSON object. "
            f"Raw response: {cleaned[:4000]}"
        )

    # --------------------------------------------------------
    # Find matching closing brace.
    #
    # We must ignore braces that appear inside JSON strings.
    # --------------------------------------------------------

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(cleaned)):
        char = cleaned[index]

        # Handle escaped characters inside strings.
        if escaped:
            escaped = False
            continue

        if char == "\\" and in_string:
            escaped = True
            continue

        # Toggle JSON string state.
        if char == '"':
            in_string = not in_string
            continue

        # Ignore braces inside strings.
        if in_string:
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                return cleaned[start:index + 1]

    raise EvaluationGenerationError(
        "LLM returned an incomplete/truncated JSON object. "
        f"Raw response: {cleaned[:4000]}"
    )


# ============================================================
# Answer Evaluation Agent
# ============================================================

class AnswerEvaluationAgent:
    """
    Generates a structured evaluation of a student's answer
    using the configured LLM service.
    """

    def __init__(
        self,
        llm: LLMService | None = None,
    ):
        self.llm = llm or LLMService()

    def evaluate(
        self,
        *,
        question_text: str,
        max_marks: int,
        student_answer: str,
        baseline_answer: str,
        key_concepts: list[str],
        expected_points: list[str],
        factors: list[dict],
    ) -> GeneratedEvaluation:

        factor_text = "\n".join(
            (
                f"- {factor['name']} "
                f"({factor['weight_percent']}%): "
                f"{factor['description']}"
            )
            for factor in factors
        )

        if not factor_text:
            factor_text = "No additional factors."

        prompt = f"""QUESTION ({max_marks} marks):
{question_text}

APPROVED BASELINE / REFERENCE ANSWER:
{baseline_answer}

KEY CONCEPTS:
{", ".join(key_concepts) or "None"}

EXPECTED POINTS:
{chr(10).join("- " + p for p in expected_points) or "None"}

APPROVED ADDITIONAL FACTORS (25% total):
{factor_text}

STUDENT ANSWER:
{student_answer or "[NO ANSWER PROVIDED]"}

Evaluate the student answer now.

Remember:
- Return ONLY valid JSON.
- No markdown.
- No explanation outside the JSON.
- baseline_ratio must be between 0 and 1.
- Each factor ratio must be between 0 and 1.
"""

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self.llm.chat(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt,
                    temperature=0.0,
                    max_tokens=1400,
                )
                raw_content = response.content.strip()
                if not raw_content:
                    raise EvaluationGenerationError("LLM returned an empty evaluation response.")
                cleaned = _extract_json_object(raw_content)
                try:
                    payload = json.loads(cleaned)
                except json.JSONDecodeError as exc:
                    raise EvaluationGenerationError(
                        f"LLM returned malformed JSON. JSON error: {exc}. Raw response: {raw_content[:2000]}"
                    ) from exc
                try:
                    return GeneratedEvaluation.model_validate(payload)
                except ValidationError as exc:
                    raise EvaluationGenerationError(
                        f"LLM JSON failed evaluation schema validation: {exc}. Payload: {cleaned[:2000]}"
                    ) from exc
            except EvaluationGenerationError as exc:
                last_error = exc
            except Exception as exc:
                last_error = exc
            if attempt == 0:
                continue

        raise EvaluationGenerationError(
            f"Evaluation generation failed after 2 attempts: {last_error}"
        ) from last_error

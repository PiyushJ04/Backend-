from __future__ import annotations

from dataclasses import dataclass

from huggingface_hub import InferenceClient

from app.core.config import settings


class LLMConfigurationError(RuntimeError):
    """Raised when the LLM provider is not configured correctly."""


class LLMGenerationError(RuntimeError):
    """Raised when the configured LLM cannot generate a response."""


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str


class LLMService:
    """Provider-agnostic application wrapper around Hugging Face inference."""

    def __init__(self) -> None:
        if not settings.hf_token:
            raise LLMConfigurationError(
                "HF_TOKEN is not configured. Add a Hugging Face User Access Token "
                "to the backend environment before using the LLM."
            )

        self.model = settings.llm_model
        self.client = InferenceClient(
            model=self.model,
            provider=settings.hf_provider,
            api_key=settings.hf_token,
            timeout=settings.llm_timeout_seconds,
        )

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> LLMResponse:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  
            raise LLMGenerationError(f"Hugging Face inference failed: {exc}") from exc

        content = completion.choices[0].message.content
        if not content or not content.strip():
            raise LLMGenerationError("The LLM returned an empty response")

        return LLMResponse(content=content.strip(), model=self.model)
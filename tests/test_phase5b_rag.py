from types import SimpleNamespace

from app.services.ai.embedding import EmbeddingService
from app.services.ai.reference_answer import ReferenceAnswerAgent


def test_embedding_output_1d_is_normalized():
    vector = EmbeddingService._to_sentence_vector([3.0, 4.0])
    assert len(vector) == 2
    assert round(vector[0], 6) == 0.6
    assert round(vector[1], 6) == 0.8


def test_embedding_output_2d_is_mean_pooled():
    vector = EmbeddingService._to_sentence_vector([[1.0, 0.0], [0.0, 1.0]])
    assert len(vector) == 2
    assert round(vector[0], 6) == round(2 ** -0.5, 6)
    assert round(vector[1], 6) == round(2 ** -0.5, 6)


def test_embedding_output_3d_uses_first_batch():
    vector = EmbeddingService._to_sentence_vector([[[1.0, 0.0], [0.0, 1.0]]])
    assert len(vector) == 2
    assert round(vector[0], 6) == round(2 ** -0.5, 6)


def test_reference_agent_keeps_phase5a_manual_context_compatibility():
    class FakeLLM:
        def chat(self, **kwargs):
            return SimpleNamespace(
                content='{"reference_answer":"Answer", "key_concepts":[], '
                        '"expected_points":[], "limitations":[]}'
            )

    draft = ReferenceAnswerAgent(llm=FakeLLM()).generate(
        question_no="1",
        question_text="Define OOP.",
        max_marks=2,
        supplemental_context=["OOP is a programming paradigm."],
    )
    assert draft.reference_answer == "Answer"

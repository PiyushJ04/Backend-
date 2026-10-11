from app.schemas.reference_answer import ReferenceAnswerDraft
from app.services.ai.reference_answer import ReferenceAnswerAgent


class FakeLLM:
    def __init__(self, content: str):
        self.content = content

    def chat(self, **kwargs):
        class Response:
            pass
        response = Response()
        response.content = self.content
        response.model = "fake"
        return response


def test_reference_answer_agent_validates_structured_output():
    llm = FakeLLM(
        '{"reference_answer":"A class is a blueprint; an object is an instance.",'
        '"key_concepts":["class","object"],'
        '"expected_points":["define class","define object"],'
        '"limitations":[]}'
    )
    draft = ReferenceAnswerAgent(llm=llm).generate(
        question_no="6",
        question_text="Differentiate between a class and an object.",
        max_marks=4,
        academic_context=["A class is a blueprint. An object is an instance of a class."],
    )
    assert isinstance(draft, ReferenceAnswerDraft)
    assert draft.key_concepts == ["class", "object"]


def test_reference_answer_agent_accepts_markdown_json_fence():
    llm = FakeLLM(
        '```json\n'
        '{"reference_answer":"Answer", "key_concepts":[], '
        '"expected_points":[], "limitations":[]}\n'
        '```'
    )
    draft = ReferenceAnswerAgent(llm=llm).generate(
        question_no="1",
        question_text="Define OOP.",
        max_marks=2,
        academic_context=["OOP is a programming paradigm."],
    )
    assert draft.reference_answer == "Answer"

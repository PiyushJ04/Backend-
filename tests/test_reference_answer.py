from types import SimpleNamespace

from app.schemas.reference_answer import ReferenceAnswerDraft
from app.services.ai.reference_answer import ReferenceAnswerAgent


def words(n: int) -> str:
    return " ".join(f"concept{idx}" for idx in range(n))


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def chat(self, **kwargs):
        content = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return SimpleNamespace(content=content, model="fake")


def test_reference_answer_agent_accepts_plain_academic_text_with_code():
    answer = words(330) + '\n\n```java\nclass Student { String name; int marks; }\nStudent s1 = new Student();\n```'
    draft = ReferenceAnswerAgent(llm=FakeLLM([answer])).generate(
        question_no="1",
        question_text="(a) Explain object creation in Java with an example.",
        max_marks=8,
    )
    assert isinstance(draft, ReferenceAnswerDraft)
    assert "Student s1 = new Student();" in draft.reference_answer
    assert len(draft.reference_answer.split()) >= 300


def test_short_answer_is_regenerated_without_json():
    short = words(120)
    long = words(320)
    llm = FakeLLM([short, long])
    draft = ReferenceAnswerAgent(llm=llm).generate(
        question_no="1",
        question_text="(a) Explain constructors.",
        max_marks=8,
    )
    assert len(draft.reference_answer.split()) >= 300
    assert llm.calls == 2


def test_multiple_subquestions_are_generated_independently():
    a = words(310)
    b = words(305)
    llm = FakeLLM([a, b])
    draft = ReferenceAnswerAgent(llm=llm).generate(
        question_no="2",
        question_text="(a) Explain A. [8 marks] (b) Explain B. [8 marks]",
        max_marks=8,
    )
    assert "(a)" in draft.reference_answer
    assert "(b)" in draft.reference_answer
    assert len(draft.reference_answer.split()) >= 600
    assert llm.calls == 2


def test_long_answer_is_not_rejected_by_an_artificial_upper_limit():
    answer = words(700)
    draft = ReferenceAnswerAgent(llm=FakeLLM([answer])).generate(
        question_no="1",
        question_text="(a) Explain the topic in depth.",
        max_marks=8,
    )
    assert len(draft.reference_answer.split()) >= 700


def test_code_quotes_and_backslashes_are_safe_because_json_is_not_used():
    answer = words(300) + r'''\n\n```java
System.out.println("Hello");
String path = "C:\\temp\\data";
```
'''
    draft = ReferenceAnswerAgent(llm=FakeLLM([answer])).generate(
        question_no="1",
        question_text="(a) Explain the code with an example.",
        max_marks=8,
    )
    assert 'System.out.println("Hello");' in draft.reference_answer
    assert "C:\\temp" in draft.reference_answer

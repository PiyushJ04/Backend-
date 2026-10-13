from app.services.student_answer_service import StudentAnswerService


def test_student_identifier_from_filename():
    assert StudentAnswerService.student_identifier_from_filename("Answer_Sheet_23") == "23"
    assert StudentAnswerService.student_identifier_from_filename("STU-104") == "STU-104"


def test_segment_answers_by_question_number():
    class Q:
        def __init__(self, id, no): self.id, self.question_no = id, no
    questions = [Q("q1", "1"), Q("q2", "2"), Q("q10", "10")]
    pages = [(1, "1. Define encapsulation.\nEncapsulation hides data.\n2) Explain inheritance.\nInheritance reuses behavior.\n10: Explain polymorphism.\nPolymorphism allows runtime dispatch.")]
    segments = StudentAnswerService.segment_answers(pages, questions)
    assert "hides data" in segments["q1"].text
    assert "reuses behavior" in segments["q2"].text
    assert "runtime dispatch" in segments["q10"].text


def test_question_ten_does_not_match_question_one():
    class Q:
        def __init__(self, id, no): self.id, self.question_no = id, no
    questions = [Q("q1", "1"), Q("q10", "10")]
    segments = StudentAnswerService.segment_answers([(1, "10. Ten answer")], questions)
    assert "q1" not in segments
    assert "Ten answer" in segments["q10"].text

import pytest

from app.services.question_paper_parser import (
    QuestionPaperParseError,
    QuestionPaperParser,
)


def test_parse_sectioned_theory_paper_exactly():
    text = """
    Object-Oriented Programming (Theory) - Demo Paper | Page 1
    OBJECT-ORIENTED PROGRAMMING (OOP)
    General Instructions:
    1. Attempt all questions as directed in each section.
    2. Marks are shown against each question.
    3. Draw neat diagrams and give suitable examples wherever required.
    4. Write answers in clear, well-organised points.
    SECTION A: Very Short Answer Questions (5 x 2 = 10 Marks)
    Attempt ALL questions. Answer each in 2-3 lines.
    1. Define Object-Oriented Programming and list its main features. [2]
    2. What is a destructor? When is it called? [2]
    3. What is the role of the final keyword in Java? [2]
    4. What is dynamic (late) binding? [2]
    5. Define message passing in object-oriented programming. [2]
    SECTION B: Short Answer Questions (5 x 4 = 20 Marks)
    Attempt any FIVE of the following six questions.
    6. Differentiate between a class and an object with a suitable example. [4]
    7. What is a constructor? Explain the different types of constructors. [4]
    8. Explain the difference between method overloading and method overriding. [4]
    9. What is abstraction? How does it differ from encapsulation? [4]
    10. Explain the static keyword and where it can be used. [4]
    11. What is the difference between an abstract class and an interface? [4]
    SECTION C: Long Answer Questions (2 x 10 = 20 Marks)
    Attempt any TWO of the following four questions.
    12. (a) Explain the four pillars of OOP with a real-world example for each. [6]
    (b) List any four advantages of OOP over procedural programming. [4]
    13. (a) Explain the different types of inheritance with neat diagrams. [6]
    (b) Why does the diamond problem occur, and how do C++ and Java handle it? [4]
    14. (a) What is polymorphism? Explain its types with suitable examples. [6]
    (b) Differentiate between compile-time (static) and runtime (dynamic) polymorphism. [4]
    15. (a) Explain the access specifiers using a comparison table. [6]
    (b) Explain the purpose of the this and super keywords with examples. [4]
    *** END OF QUESTION PAPER ***
    MARKING GUIDE (For Teacher Use Only)
    Q1. This must never be parsed as a question from the answer key.
    """
    questions = QuestionPaperParser.parse(text)

    assert len(questions) == 15
    assert [q.question_no for q in questions] == [str(i) for i in range(1, 16)]
    assert [q.max_marks for q in questions] == [2] * 5 + [4] * 6 + [10] * 4
    assert [q.section for q in questions] == ["A"] * 5 + ["B"] * 6 + ["C"] * 4
    assert [q.question_type for q in questions] == ["very_short"] * 5 + ["short"] * 6 + ["long"] * 4
    assert all("MARKING GUIDE" not in q.question_text.upper() for q in questions)
    assert all("END OF QUESTION PAPER" not in q.question_text.upper() for q in questions)
    assert "SECTION B" not in questions[4].question_text
    assert "SECTION C" not in questions[10].question_text
    assert "(b) List any four advantages" in questions[11].question_text


def test_mcq_section_gets_section_marks_and_type():
    text = """
    SECTION A: Multiple Choice Questions (10 x 1 = 10 Marks)
    Attempt all questions. Choose the correct option.
    1. Which is a pillar of OOP?
    (a) Encapsulation (b) Compilation
    2. Which keyword inherits a class in Java? [1]
    SECTION B: Short Answer Questions (1 x 4 = 4 Marks)
    3. Explain abstraction. [4]
    *** END OF QUESTION PAPER ***
    ANSWER KEY
    1. a
    """
    questions = QuestionPaperParser.parse(text)
    assert [(q.question_no, q.max_marks, q.section, q.question_type) for q in questions] == [
        ("1", 1, "A", "mcq"),
        ("2", 1, "A", "mcq"),
        ("3", 4, "B", "short"),
    ]


def test_unsectioned_paper_keeps_existing_numbered_question_support():
    text = """
    UNIVERSITY EXAMINATION
    Time: 2 Hours
    Instructions: answer all questions.
    Q1. Define operating system. [5 Marks]
    Explain its main functions.
    Q2) Compare process and thread. (10)
    Q3: What is scheduling? 5 marks
    """
    questions = QuestionPaperParser.parse(text)

    assert len(questions) == 3
    assert questions[0].question_no == "1"
    assert questions[0].max_marks == 5
    assert "main functions" in questions[0].question_text
    assert questions[1].max_marks == 10
    assert questions[2].max_marks == 5


def test_parser_is_deterministic_and_ignores_unrelated_text():
    text = """
    UNIVERSITY EXAMINATION
    Time: 2 Hours

    1. Explain normalization. [8]
    Some additional line.

    2. Explain indexing. [7]
    """
    first = QuestionPaperParser.parse(text)
    second = QuestionPaperParser.parse(text)

    assert first == second
    assert [q.max_marks for q in first] == [8, 7]


def test_teacher_material_after_end_marker_is_never_parsed():
    text = """
    SECTION A: Very Short Answer Questions (2 x 2 = 4 Marks)
    1. Define encapsulation. [2]
    2. Define abstraction. [2]
    *** END OF QUESTION PAPER ***
    MARKING GUIDE
    Q1. Encapsulation is...
    Q2. Abstraction is...
    """
    questions = QuestionPaperParser.parse(text)
    assert len(questions) == 2
    assert [q.question_no for q in questions] == ["1", "2"]


def test_sectioned_paper_without_marks_fails_validation():
    text = """
    SECTION A: Very Short Answer Questions
    1. Define encapsulation.
    """
    with pytest.raises(QuestionPaperParseError, match="Could not determine marks"):
        QuestionPaperParser.parse(text)

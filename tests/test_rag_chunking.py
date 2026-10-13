from app.services.ai.rag import chunk_text


def test_chunk_text_preserves_overlap():
    words = [f"w{i}" for i in range(10)]
    chunks = chunk_text(" ".join(words), chunk_size=6, overlap=2)
    assert chunks == [
        "w0 w1 w2 w3 w4 w5",
        "w4 w5 w6 w7 w8 w9",
    ]


def test_chunk_text_rejects_invalid_overlap():
    try:
        chunk_text("one two three", chunk_size=3, overlap=3)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

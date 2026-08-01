import pytest
from workers.tasks import split_transcript

def test_split_transcript_verbatim_golden_handoff():
    sample_text = (
        "Welcome to the Q3 earnings call. Revenue grew by 15% year over year. "
        "Now we will open the call up for questions. "
        "Operator, please go ahead. Analyst 1: Can you detail margin performance?"
    )
    prepared, qa, is_verbatim = split_transcript(sample_text)
    assert is_verbatim is True
    assert "Welcome to the Q3 earnings call." in prepared
    assert "Analyst 1: Can you detail margin performance?" in qa

def test_split_transcript_qa_session_marker():
    sample_text = (
        "Prepared Remarks: Strong cash flow performance across segments. "
        "We will now begin the question-and-answer session. "
        "Host: First question comes from John Doe."
    )
    prepared, qa, is_verbatim = split_transcript(sample_text)
    assert is_verbatim is True
    assert "Strong cash flow" in prepared
    assert "John Doe" in qa

def test_split_transcript_summary_article_fallback():
    sample_text = "Apple reported Q3 earnings today with beating expectations on top and bottom line."
    prepared, qa, is_verbatim = split_transcript(sample_text)
    assert is_verbatim is False
    assert prepared == sample_text
    assert qa == ""

def test_split_transcript_empty_text():
    prepared, qa, is_verbatim = split_transcript("")
    assert is_verbatim is False
    assert prepared == ""
    assert qa == ""

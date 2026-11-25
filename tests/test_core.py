from agent.answers import answer
from agent.discover import matches
from agent.models import Job
from agent.rag import Index, chunk

PROFILE = {"first_name": "Varun", "email": "v@example.com", "work_authorized_us": "Yes",
           "needs_sponsorship": "No", "salary_expectation": "", "eeo_default": "Decline to self-identify"}
JOB = Job("greenhouse", "Acme", "1", "ML Intern", "Remote", "http://x", "Build ML systems")
IDX = Index(chunk("Built a PyTorch object tracker for drones that ran at 30 fps.\n\n"
                  "Led a hackathon team to build a battery-health model using logistic regression."))


def fake_llm(label, job, ctx, words):
    return {"answer": "I built a PyTorch object tracker.", "confidence": 0.9, "grounded": True}


def test_facts_from_profile():
    assert answer("Email address", JOB, PROFILE, IDX).value == "v@example.com"
    assert answer("Will you now or in the future require sponsorship?", JOB, PROFILE, IDX).value == "No"


def test_sensitive_goes_to_human():
    a = answer("What are your salary expectations?", JOB, PROFILE, IDX)
    assert a.needs_review and not a.value
    assert answer("Gender", JOB, PROFILE, IDX).value == "Decline to self-identify"


def test_llm_used_for_open_questions_only_when_grounded():
    a = answer("Describe a computer vision project you built", JOB, PROFILE, IDX, llm=fake_llm)
    assert a.source == "llm" and not a.needs_review
    low = answer("Describe a computer vision project you built", JOB, PROFILE, IDX,
                 llm=lambda *x: {"answer": "x", "confidence": 0.3, "grounded": False})
    assert low.needs_review


def test_no_context_means_review():
    assert answer("Tell us about quantum cooking", JOB, PROFILE, Index([]), llm=fake_llm).needs_review


def test_title_filter():
    prefs = {"include_title_keywords": ["intern"], "must_match_any": ["ml"], "exclude_keywords": ["senior"]}
    assert matches(JOB, prefs)
    assert not matches(Job("lever", "A", "2", "Senior ML Intern", "", "", ""), prefs)
    assert not matches(Job("lever", "A", "3", "Sales Intern", "", "", "no match"), prefs)

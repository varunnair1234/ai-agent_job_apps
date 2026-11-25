"""Answer form questions. Factual fields come from the profile; only open-ended ones use the LLM."""
import json
import os
import re

from .models import Answer, Job
from .rag import Index

# Questions that always go to a human, whatever the model says.
ALWAYS_REVIEW = re.compile(
    r"salary|compensation|pay expectation|criminal|felony|convicted|visa|veteran|disab|"
    r"i certify|i attest|under penalty|referr|relative|government official|non-?compete", re.I)
EEO = re.compile(r"gender|race|ethnic|hispanic|sexual orientation|transgender|pronoun", re.I)

# (regex on label, profile key). First match wins; order matters.
FACT_RULES = [
    (r"first name|given name", "first_name"),
    (r"last name|family name|surname", "last_name"),
    (r"e-?mail", "email"),
    (r"phone|mobile", "phone"),
    (r"linkedin", "linkedin"),
    (r"github", "github"),
    (r"website|portfolio|personal site", "website"),
    (r"sponsor", "needs_sponsorship"),
    (r"authori[sz]ed to work|legally (authori[sz]ed|eligible)|work authori[sz]ation", "work_authorized_us"),
    (r"relocat", "willing_to_relocate"),
    (r"start date|available to start|when can you start", "available_start"),
    (r"graduat", "graduation"),
    (r"school|university|college", "school"),
    (r"degree", "degree"),
    (r"current location|city|where are you (based|located)|location", "location"),
]

SYSTEM = (
    "You answer job-application questions on behalf of the candidate. Use ONLY facts found in the "
    "CONTEXT. Never invent employers, dates, metrics, skills or projects. If the context does not "
    "support a good answer, say so. Write in first person, concrete, no fluff, and keep it under "
    "{words} words. Reply with JSON only: "
    '{{"answer": str, "confidence": number 0-1, "grounded": bool}}'
)


def factual(label: str, profile: dict) -> Answer | None:
    for rx, key in FACT_RULES:
        if re.search(rx, label, re.I):
            val = str(profile.get(key, "")).strip()
            if val:
                return Answer(label, val, "profile")
            return Answer(label, "", "none", 0.0, True, f"profile.{key} is empty")
    return None


def _llm(label: str, job: Job, ctx: list[str], words: int) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        max_tokens=700,
        system=SYSTEM.format(words=words),
        messages=[{"role": "user", "content": (
            f"JOB: {job.title} at {job.company}\nJOB DESCRIPTION: {job.description[:2500]}\n\n"
            f"CONTEXT (candidate facts):\n---\n" + "\n---\n".join(ctx) + f"\n\nQUESTION: {label}")}],
    )
    text = msg.content[0].text
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def answer(label: str, job: Job, profile: dict, index: Index, options: list | None = None,
           min_conf: float = 0.7, llm=_llm) -> Answer:
    if ALWAYS_REVIEW.search(label):
        pre = factual(label, profile)
        if pre and pre.source == "profile":
            return pre
        return Answer(label, "", "none", 0.0, True, "sensitive question: human decides")
    if EEO.search(label):
        return Answer(label, profile.get("eeo_default", "Decline to self-identify"), "profile")
    f = factual(label, profile)
    if f:
        return f

    hits = index.search(f"{label} {job.title} {job.description[:300]}")
    if not hits:
        return Answer(label, "", "none", 0.0, True, "nothing in your notes supports an answer")
    words = 60 if len(label) < 80 else 150
    try:
        r = llm(label, job, [c for _, c in hits], words)
    except Exception as e:
        return Answer(label, "", "none", 0.0, True, f"LLM error: {e}")
    conf = float(r.get("confidence", 0))
    ok = bool(r.get("grounded")) and conf >= min_conf and bool(r.get("answer"))
    return Answer(label, r.get("answer", ""), "llm", conf, not ok, "" if ok else "low confidence / not grounded")

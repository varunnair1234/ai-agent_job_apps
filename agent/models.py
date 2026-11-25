from dataclasses import dataclass, field


@dataclass
class Job:
    ats: str
    company: str
    job_id: str
    title: str
    location: str
    url: str
    description: str = ""

    @property
    def key(self) -> str:
        return f"{self.ats}:{self.company.lower()}:{self.job_id}"


@dataclass
class Answer:
    label: str
    value: str
    source: str  # "profile" | "llm" | "none"
    confidence: float = 1.0
    needs_review: bool = False
    reason: str = ""


@dataclass
class FormField:
    label: str
    kind: str  # text | textarea | select | file | checkbox | radio
    required: bool = False
    options: list = field(default_factory=list)
    handle: object = None

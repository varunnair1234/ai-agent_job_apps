# job-apply-agent

Finds internship postings on Greenhouse / Lever / Ashby, fills the application form from your profile,
answers open-ended questions with RAG over your resume + project notes, and tracks everything in SQLite.

## Setup
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
export ANTHROPIC_API_KEY=...            # optional: ANTHROPIC_MODEL=claude-sonnet-5-5
cp data/profile.example.yaml data/profile.yaml   # fill in; set resume_path
# put your resume as text in data/resume.md, and project write-ups in data/stories/*.md
```
The more detail in resume.md and stories/, the better the grounded answers.

## Use
```
python main.py discover                          # list new matching jobs
python main.py run --mode dry --limit 5          # fill forms, log answers, submit nothing
python main.py run --mode review --limit 10      # you approve each one in a visible browser
python main.py run --mode auto --limit 30        # auto-submit only clean Greenhouse/Lever/Ashby forms
python main.py status --status pending_review    # what's waiting on you
python -m pytest tests
```

## Safety rules built in
- Factual fields (name, email, work auth, sponsorship, grad date) come from profile.yaml only, never the LLM.
- Salary, legal attestations, referrals, etc. always go to you. EEO questions default to "decline".
- LLM answers must be grounded in your notes with confidence >= 0.7, else the job goes to `pending_review`.
- CAPTCHAs, logins and account creation are never bypassed: those jobs are marked `needs_human`.
- Dedupes jobs and caps applications per company.

## Known limits
- Tested offline only (unit tests). Run `--mode dry` against real postings first and check the logged answers.
- Radio/checkbox questions are left for you. Workday/iCIMS/Taleo are not supported.
- Start with `review`; move to `auto` only after dry runs look right.

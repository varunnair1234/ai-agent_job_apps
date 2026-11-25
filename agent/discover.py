"""Fetch postings from public Greenhouse / Lever / Ashby job-board endpoints and filter them."""
import re
import requests

from .models import Job

TIMEOUT = 20


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def fetch_greenhouse(name: str, token: str) -> list[Job]:
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                     params={"content": "true"}, timeout=TIMEOUT)
    r.raise_for_status()
    return [Job("greenhouse", name, str(j["id"]), j["title"],
                (j.get("location") or {}).get("name", ""), j["absolute_url"],
                _strip(j.get("content", ""))) for j in r.json().get("jobs", [])]


def fetch_lever(name: str, token: str) -> list[Job]:
    r = requests.get(f"https://api.lever.co/v0/postings/{token}", params={"mode": "json"}, timeout=TIMEOUT)
    r.raise_for_status()
    return [Job("lever", name, j["id"], j["text"],
                (j.get("categories") or {}).get("location", ""), j["hostedUrl"],
                j.get("descriptionPlain", "")) for j in r.json()]


def fetch_ashby(name: str, token: str) -> list[Job]:
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{token}", timeout=TIMEOUT)
    r.raise_for_status()
    return [Job("ashby", name, j["id"], j["title"], j.get("location", ""), j["jobUrl"],
                j.get("descriptionPlain", "")) for j in r.json().get("jobs", [])]


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


def matches(job: Job, prefs: dict) -> bool:
    title = job.title.lower()
    text = f"{title} {job.description[:1500].lower()}"
    if any(k in title for k in prefs.get("exclude_keywords", [])):
        return False
    if not any(k in title for k in prefs.get("include_title_keywords", [])):
        return False
    must = prefs.get("must_match_any", [])
    return not must or any(re.search(rf"\b{re.escape(k)}\b", text) for k in must)


def discover(profile: dict) -> list[Job]:
    jobs: list[Job] = []
    for c in profile.get("companies", []):
        try:
            found = FETCHERS[c["ats"]](c["name"], c["token"])
        except Exception as e:  # one bad board shouldn't stop the run
            print(f"[discover] {c['name']}: {e}")
            continue
        jobs += [j for j in found if matches(j, profile.get("preferences", {}))]
    return jobs

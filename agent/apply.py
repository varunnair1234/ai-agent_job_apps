"""Browser form filler (Playwright). Fills a posting's application form from your profile + RAG answers.

It never solves CAPTCHAs, creates accounts or logs in: those jobs are handed back to you.
"""
from .answers import answer
from .models import Answer, FormField, Job

AUTO_ATS = {"greenhouse", "lever", "ashby"}  # only these may auto-submit
CAPTCHA_HINTS = ("recaptcha", "hcaptcha", "turnstile", "captcha")

LABEL_JS = """el => {
  const id = el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
  if (id) return id.innerText;
  if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
  const lb = el.getAttribute('aria-labelledby');
  if (lb) { const t = document.getElementById(lb); if (t) return t.innerText; }
  const wrap = el.closest('label, .field, .application-field, [class*="field"], li, div');
  return wrap ? wrap.innerText.split('\\n')[0] : (el.placeholder || el.name || '');
}"""


def has_captcha(page) -> bool:
    html = page.content().lower()
    return any(h in html for h in CAPTCHA_HINTS) and page.locator("iframe[src*='captcha'], .g-recaptcha, .h-captcha, .cf-turnstile").count() > 0


def collect_fields(page) -> list[FormField]:
    fields = []
    for el in page.locator("form input:not([type=hidden]):not([type=submit]), form textarea, form select").all():
        try:
            if not el.is_visible() and el.get_attribute("type") != "file":
                continue
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            typ = (el.get_attribute("type") or "text").lower()
            kind = "file" if typ == "file" else "select" if tag == "select" else "textarea" if tag == "textarea" \
                else typ if typ in ("checkbox", "radio") else "text"
            label = " ".join(str(el.evaluate(LABEL_JS)).split())[:300]
            opts = el.locator("option").all_inner_texts() if kind == "select" else []
            req = el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true"
            fields.append(FormField(label, kind, req, opts, el))
        except Exception:
            continue
    return fields


def fill_form(page, job: Job, profile: dict, index) -> list[Answer]:
    results: list[Answer] = []
    for f in collect_fields(page):
        if f.kind == "file":
            if "resume" in f.label.lower() or "cv" in f.label.lower() or not f.label:
                f.handle.set_input_files(profile["resume_path"])
                results.append(Answer(f.label or "resume", profile["resume_path"], "profile"))
            continue
        if f.kind in ("checkbox", "radio"):
            continue  # handled by humans in review; too ambiguous to guess
        a = answer(f.label, job, profile, index, f.options)
        results.append(a)
        if a.needs_review or not a.value:
            continue
        try:
            if f.kind == "select":
                match = next((o for o in f.options if a.value.lower() in o.lower()), None)
                if match:
                    f.handle.select_option(label=match)
                else:
                    a.needs_review, a.reason = True, "no matching dropdown option"
            else:
                f.handle.fill(a.value)
        except Exception as e:
            a.needs_review, a.reason = True, f"fill failed: {e}"
    return results


def apply(job: Job, profile: dict, index, mode: str, headless: bool = True) -> tuple[str, str]:
    """Returns (status, notes). mode: review | auto | dry."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=(headless and mode != "review"))
        page = browser.new_page()
        page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        apply_btn = page.get_by_role("link", name="Apply", exact=False)
        if page.locator("form input").count() == 0 and apply_btn.count():
            apply_btn.first.click()
            page.wait_for_timeout(1500)
        if has_captcha(page):
            browser.close()
            return "needs_human", "CAPTCHA present"
        answers = fill_form(page, job, profile, index)
        flagged = [a for a in answers if a.needs_review]
        notes = "; ".join(f"{a.label[:50]} -> {a.reason}" for a in flagged)

        if mode == "dry":
            browser.close()
            return "dry_run", notes
        if mode == "review" or flagged or job.ats not in AUTO_ATS:
            if mode != "review":
                browser.close()
                return "pending_review", notes or "ATS not on auto list"
            print(f"\n{job.company} - {job.title}\n  flagged: {notes or 'none'}")
            input("  Fix anything in the browser, then press Enter to submit (Ctrl+C to skip)... ")
        page.get_by_role("button", name="Submit", exact=False).first.click()
        page.wait_for_timeout(3000)
        browser.close()
        return "submitted", notes

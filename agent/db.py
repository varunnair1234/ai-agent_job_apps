import sqlite3
import time

SCHEMA = """CREATE TABLE IF NOT EXISTS applications(
  job_key TEXT PRIMARY KEY, company TEXT, title TEXT, url TEXT,
  status TEXT, notes TEXT, updated REAL)"""


class DB:
    def __init__(self, path="data/applications.db"):
        self.c = sqlite3.connect(path)
        self.c.execute(SCHEMA)

    def seen(self, key: str) -> bool:
        return self.c.execute("SELECT 1 FROM applications WHERE job_key=?", (key,)).fetchone() is not None

    def company_count(self, company: str) -> int:
        return self.c.execute("SELECT COUNT(*) FROM applications WHERE lower(company)=lower(?) AND status IN "
                              "('submitted','pending_review')", (company,)).fetchone()[0]

    def save(self, job, status: str, notes: str = ""):
        self.c.execute("INSERT OR REPLACE INTO applications VALUES(?,?,?,?,?,?,?)",
                       (job.key, job.company, job.title, job.url, status, notes, time.time()))
        self.c.commit()

    def rows(self, status: str | None = None):
        q = "SELECT company,title,status,url,notes FROM applications"
        args = ()
        if status:
            q += " WHERE status=?"
            args = (status,)
        return self.c.execute(q + " ORDER BY updated DESC", args).fetchall()

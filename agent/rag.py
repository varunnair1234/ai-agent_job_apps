"""Tiny retrieval index over your resume and story files.

TF-IDF keeps this dependency-light and offline. To upgrade, replace `Index` with an embedding
model + vector store (Chroma / pgvector); the `search()` interface stays the same.
"""
import glob
import os
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def chunk(text: str, max_chars: int = 700) -> list[str]:
    out, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(cur) + len(para) > max_chars and cur:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{para}".strip()
    if cur:
        out.append(cur)
    return out


class Index:
    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)) if chunks else None
        self.mat = self.vec.fit_transform(chunks) if chunks else None

    @classmethod
    def from_dir(cls, data_dir: str = "data") -> "Index":
        files = [os.path.join(data_dir, "resume.md")] + sorted(glob.glob(os.path.join(data_dir, "stories", "*.md")))
        chunks: list[str] = []
        for f in files:
            if os.path.exists(f):
                chunks += chunk(open(f, encoding="utf-8").read())
        return cls(chunks)

    def search(self, query: str, k: int = 4) -> list[tuple[float, str]]:
        if not self.chunks:
            return []
        sims = cosine_similarity(self.vec.transform([query]), self.mat)[0]
        top = sims.argsort()[::-1][:k]
        return [(float(sims[i]), self.chunks[i]) for i in top if sims[i] > 0]

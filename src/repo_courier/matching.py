from __future__ import annotations

import re


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value.lower()).strip()


def interest_terms(interest: str) -> list[str]:
    normalized = normalize(interest)
    terms = [normalized]
    terms.extend(part for part in normalized.split() if len(part) >= 2)
    return list(dict.fromkeys(term for term in terms if term))


def contains(text: str, term: str) -> bool:
    if not term:
        return False
    return f" {term} " in f" {text} " or term in text.split()

"""Voice interview: the question script + deterministic answer parsing.

Parsing is pure/heuristic so the interview works with no API key. It handles spoken numbers
("twenty-eight thousand five hundred" -> 28500), yes/no, provinces, and names (with a spelling
read-back for confirmation). Claude can refine this later; it never decides eligibility.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Question:
    id: str
    field: str
    prompt: str
    type: str                 # text | number | bool | enum
    unit: Optional[str] = None  # money | years | None
    spell_check: bool = False


QUESTIONS: list[Question] = [
    Question("name", "first_name", "What's your first name?", "text", spell_check=True),
    Question("province", "province", "Which province or territory do you live in?", "enum"),
    Question("age", "age", "How old are you?", "number", unit="years"),
    Question("income", "annual_net_income",
             "Roughly what was your net income last year, in dollars?", "number", unit="money"),
    Question("dental", "has_private_dental_insurance",
             "Do you have private or workplace dental insurance?", "bool"),
    Question("medical", "out_of_pocket_medical_annual",
             "About how much did you pay out of pocket for medical costs last year?", "number", unit="money"),
    Question("drugs", "prescription_costs_annual",
             "About how much do you spend on prescription medications a year?", "number", unit="money"),
    Question("impairment", "has_severe_prolonged_impairment",
             "Do you have a severe and prolonged physical or mental impairment?", "bool"),
    Question("caregiver", "is_caregiver",
             "Do you care for a dependant with a physical or mental impairment?", "bool"),
    Question("taxes", "filed_taxes_last_year", "Did you file your taxes last year?", "bool"),
]

FIELD_INDEX: dict[str, Question] = {q.field: q for q in QUESTIONS}


@dataclass
class ParseResult:
    field: str
    value: Any
    raw: str
    confirmation: str
    needs_clarification: bool


# ---- number parsing (digits or spoken words) ----
_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}


def words_to_number(text: str) -> Optional[int]:
    tokens = re.findall(r"[a-z]+", text.lower())
    total = current = 0
    found = False
    for tok in tokens:
        if tok in _UNITS:
            current += _UNITS[tok]; found = True
        elif tok in _TENS:
            current += _TENS[tok]; found = True
        elif tok == "hundred":
            current = (current or 1) * 100; found = True
        elif tok in _SCALES:
            total += (current or 1) * _SCALES[tok]; current = 0; found = True
    return (total + current) if found else None


def parse_number(text: str) -> Optional[float]:
    digits = re.sub(r"[,\s$]", "", text)
    m = re.search(r"\d+(?:\.\d+)?", digits)
    if m:
        return float(m.group())
    w = words_to_number(text)
    return float(w) if w is not None else None


# ---- yes/no ----
_YES = {"yes", "yeah", "yep", "yup", "sure", "correct", "right", "do", "have", "true", "ok", "okay"}
_NO = {"no", "nope", "nah", "not", "dont", "none", "false", "never"}


def parse_bool(text: str) -> Optional[bool]:
    toks = set(re.findall(r"[a-z']+", text.lower().replace("don't", "dont")))
    if toks & _NO:
        return False
    if toks & _YES:
        return True
    return None


# ---- province ----
def parse_province(text: str) -> Optional[str]:
    t = text.lower()
    names = {
        "ontario": "ON", "quebec": "QC", "british columbia": "BC", "alberta": "AB",
        "manitoba": "MB", "saskatchewan": "SK", "nova scotia": "NS", "new brunswick": "NB",
        "newfoundland": "NL", "labrador": "NL", "prince edward island": "PE",
        "yukon": "YT", "northwest territories": "NT", "nunavut": "NU",
    }
    for name, code in names.items():
        if name in t:
            return code
    toks = set(re.findall(r"[a-z]+", t))
    codes = {"on": "ON", "qc": "QC", "bc": "BC", "ab": "AB", "mb": "MB", "sk": "SK",
             "ns": "NS", "nb": "NB", "nl": "NL", "pe": "PE", "pei": "PE",
             "yt": "YT", "nt": "NT", "nu": "NU"}
    for code_word, code in codes.items():
        if code_word in toks:
            return code
    return None


# ---- name ----
_NAME_PREFIXES = ["my name is", "the name is", "i am", "i'm", "it's", "its", "name is", "call me"]


def clean_name(text: str) -> str:
    t = text.strip().rstrip(".")
    low = t.lower()
    for p in _NAME_PREFIXES:
        if low.startswith(p):
            t = t[len(p):].strip()
            break
    return t.title()


def spelled(name: str) -> str:
    first = name.split()[0] if name.split() else name
    return "-".join(ch.upper() for ch in first if ch.isalpha())


def _clarify(q: Question, msg: str, raw: str) -> ParseResult:
    return ParseResult(q.field, None, raw, f"{msg} {q.prompt}", True)


def parse_answer(q: Question, text: str) -> ParseResult:
    text = (text or "").strip()
    if not text:
        return _clarify(q, "I didn't catch that.", text)

    if q.type == "number":
        v = parse_number(text)
        if v is None:
            return _clarify(q, "I couldn't make out a number.", text)
        if q.unit == "money":
            conf = f"I heard ${v:,.0f}. Is that right?"
        elif q.unit == "years":
            conf = f"I heard {v:,.0f} years old. Is that right?"
        else:
            conf = f"I heard {v:,.0f}. Is that right?"
        return ParseResult(q.field, v, text, conf, False)

    if q.type == "bool":
        v = parse_bool(text)
        if v is None:
            return _clarify(q, "Please answer yes or no.", text)
        return ParseResult(q.field, v, text, f"Got it — {'yes' if v else 'no'}.", False)

    if q.type == "enum" and q.field == "province":
        v = parse_province(text)
        if v is None:
            return _clarify(q, "I didn't recognize that province.", text)
        return ParseResult(q.field, v, text, f"I heard {v}. Is that correct?", False)

    # text (name)
    name = clean_name(text)
    conf = (f"I heard {name}, spelled {spelled(name)}. Is that right?"
            if q.spell_check else f"I heard {name}.")
    return ParseResult(q.field, name, text, conf, False)

"""Deterministic warning indicators; none establishes proven fraud."""
import re
from email.utils import parseaddr

CAREER = re.compile(
    r"\b(?:internships?|jobs?|career|recruit(?:er|ing|ment)?|hackathon|admissions?|"
    r"fellowship|interview|resume|résumé|scholarship)\b", re.IGNORECASE,
)
SCAM_PATTERNS = (
    ("upfront_fee", r"\b(?:upfront|registration|processing|release) fee\b"),
    ("urgency", r"\b(?:urgent|today|act now|immediately|last chance)\b"),
    ("unrealistic_pay", r"\$\s?\d{5,}|\b\d{5,}\s*(?:usd|dollars)\b"),
)
FREE_MAIL = frozenset({"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"})


def career_status(email, proposed):
    text = f"{email.sender} {email.subject} {email.body_excerpt}"
    return True if CAREER.search(text) else proposed


def scam_signals(email, existing):
    text = f"{email.subject} {email.body_excerpt}"
    detected = tuple(name for name, pattern in SCAM_PATTERNS if re.search(pattern, text, re.IGNORECASE))
    sender_domain = parseaddr(email.sender)[1].rpartition("@")[2].casefold()
    sender_warning = ("free_mail_sender",) if sender_domain in FREE_MAIL and career_status(email, False) else ()
    return tuple(dict.fromkeys(tuple(signal.strip() for signal in existing) + detected + sender_warning))

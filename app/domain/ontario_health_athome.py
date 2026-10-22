"""Ontario Health atHome: publicly funded, agency-delivered home care.

The other side of the home-care fork. Where Direct Funding is for people who self-manage their own
attendants, Ontario Health atHome arranges care FOR you: a care coordinator assesses your needs and
sets up personal support, nursing, therapy and more. Eligibility is assessment-based (valid OHIP
plus assessed need), so Covered routes and explains rather than computing an eligibility number.

Source: https://www.ontariohealthathome.ca
"""
from __future__ import annotations

SOURCE_URL = "https://www.ontariohealthathome.ca"
GETTING_STARTED_URL = "https://ontariohealthathome.ca/getting-started"
VERIFIED = "2026-10-22"

SERVICES = [
    "Personal support with bathing, dressing, meals and mobility, from a PSW",
    "Nursing (wound care, medications, monitoring) from an RN or RPN",
    "Therapy at home: physiotherapy, occupational therapy, speech-language",
    "Social work, a dietitian, and some medical supplies and equipment",
    "Connections to community supports: meals, transportation, adult day programs",
]
PROCESS = [
    "Contact Ontario Health atHome to ask for care. No doctor's referral is needed.",
    "A care coordinator assesses your needs, often with a visit to your home.",
    "They decide which services you qualify for, based on your assessed needs and local availability.",
    "You build a care plan together, and agency staff deliver the care.",
]


def route(*, ontario_resident: bool = True, has_ohip: bool = True) -> dict:
    """Route to Ontario Health atHome. Not an eligibility calculation: the care coordinator assesses."""
    fit = bool(ontario_resident and has_ohip)
    return {
        "name": "Ontario Health atHome",
        "subtitle": "Agency-arranged home care",
        "fit": fit,
        "note": ("With a valid Ontario Health Card you can ask for an assessment; the care coordinator "
                 "decides the services." if fit
                 else "Needs a valid Ontario Health Card and Ontario residency."),
        "services": SERVICES,
        "process": PROCESS,
        "source_url": SOURCE_URL,
        "getting_started_url": GETTING_STARTED_URL,
        "verified": VERIFIED,
    }

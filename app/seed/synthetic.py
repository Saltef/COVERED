"""Synthetic Canadian population for testing the screening engine at volume.

Era's CRM has no benefit-eligibility fields (income, age, disability, province), so it cannot
supply screenable people. This generates a realistic, benefits-seeking population instead: the
kind of book a pharmacy, tax app, or agency would run through /v1/eligibility. Distributions are
deliberately skewed low-to-modest income and older, because that is who is leaving benefits
unclaimed. Fully deterministic given the seed, so runs are reproducible.

Not real people. Every record is generated; nothing here is scraped or sampled from a real source.
"""
from __future__ import annotations

import random

PROVINCES = [  # rough population weights; ON over-represented so Trillium (ON-only) shows up
    ("ON", 0.42), ("QC", 0.14), ("BC", 0.16), ("AB", 0.12),
    ("MB", 0.05), ("NS", 0.04), ("SK", 0.04), ("NB", 0.03),
]
MARITAL = ["single", "married", "common_law", "widowed", "divorced", "separated"]
FIRST_NAMES = [
    "Margaret", "Robert", "Elaine", "David", "Priya", "James", "Linda", "Wei", "Fatima", "John",
    "Susan", "Ahmed", "Grace", "Daniel", "Nadia", "Paul", "Ruth", "Omar", "Helen", "Marie",
    "George", "Anita", "Frank", "Joan", "Hassan", "Beatrice", "Luc", "Carmen", "Henry", "Ingrid",
]


def _weighted(rng: random.Random, pairs: list[tuple[str, float]]) -> str:
    r, acc = rng.random(), 0.0
    for value, w in pairs:
        acc += w
        if r <= acc:
            return value
    return pairs[-1][0]


def _one(rng: random.Random) -> dict:
    province = _weighted(rng, PROVINCES)

    # ~40% seniors, 60% working-age — a benefits-seeking skew, older than the general public.
    senior = rng.random() < 0.40
    age = rng.randint(65, 88) if senior else rng.randint(19, 64)

    # Low-to-modest income skew. Net income in thousands, clamped to a plausible range.
    income = int(max(6_000, min(130_000, rng.lognormvariate(10.25, 0.55))))

    # Disability: ~18% severe/prolonged; most (but not all) of those are DTC-certified.
    impaired = rng.random() < 0.18
    dtc = impaired and rng.random() < 0.6

    # Private dental insurance: common for higher earners, rare for low-income seniors.
    p_dental = 0.15 + min(0.6, income / 110_000)
    if senior:
        p_dental *= 0.5
    dental = rng.random() < p_dental

    # Drug and other medical costs: higher with age and impairment; many have little or none.
    base_rx = (900 if senior else 250) + (1_400 if impaired else 0)
    rx = max(0, int(rng.gauss(base_rx, base_rx * 0.7))) if rng.random() < 0.7 else 0
    med = max(0, int(rng.gauss(rx * 0.6 + 200, 500)))

    caregiver = (not impaired) and rng.random() < 0.09

    return {
        "first_name": rng.choice(FIRST_NAMES),
        "province": province,
        "age": age,
        "marital_status": rng.choice(MARITAL),
        "annual_net_income": float(income),
        "has_private_dental_insurance": dental,
        "out_of_pocket_medical_annual": float(med),
        "prescription_costs_annual": float(rx),
        "has_severe_prolonged_impairment": impaired,
        "has_dtc_certificate": dtc,
        "is_caregiver": caregiver,
        "filed_taxes_last_year": rng.random() < 0.9,
        "canadian_resident": True,
    }


def generate_population(n: int = 120, seed: int = 42) -> list[dict]:
    """Return n deterministic synthetic profiles (profile dicts matching ProfileIn fields)."""
    rng = random.Random(seed)
    return [_one(rng) for _ in range(n)]

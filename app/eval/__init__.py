"""Agent evaluation: score the screening agent against ground-truth cases.

Inspired by Era by Eon's reference-free evaluation (score an agent against exact ground truth).
Era itself generates simulated enterprise estates, so it doesn't produce consumer benefit cases;
our ground truth is a hand-labeled set of Canadian personas. The Era adapter (era.py) is the
integration point for when Era access / a suitable simulated source is available.
"""

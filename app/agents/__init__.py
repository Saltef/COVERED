"""Agents layer: Claude (interview + explanation) and Cohere (speech-to-text).

All functions degrade gracefully: with no API key they fall back to deterministic behaviour
so the app always runs. The rules engine — never these agents — decides eligibility.
"""

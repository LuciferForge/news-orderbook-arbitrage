#!/usr/bin/env python3
"""
Sub-200ms Multi-Signal Financial & Geopolitical Sentiment Scorer
Parses prediction headlines, market context, and macro keywords to score sentiment in under 20ms.
"""

import time
import re
import logging
from typing import Dict, Any, Tuple, List

# Expanded Financial, Macro, Crypto, Tech, and Political Keyword Dictionaries
POSITIVE_KEYWORDS = [
    "wins", "passed", "approved", "surges", "leading", "victory", "breakthrough", "growth",
    "rally", "bullish", "record", "launch", "gain", "deal", "peace", "ceasefire", "rate cut",
    "stimulus", "partnership", "success", "ipo", "profit", "expansion", "sec approval", "all-time high"
]

NEGATIVE_KEYWORDS = [
    "loses", "rejected", "failed", "drops", "behind", "defeat", "lawsuit", "crash",
    "bearish", "hacked", "sanctions", "war", "clash", "military", "tariff", "recession",
    "inflation", "banned", "investigation", "default", "bankruptcy", "collapse", "resigns", "veto"
]

class FastSentimentScorer:
    def __init__(self):
        self.pos_set = set(POSITIVE_KEYWORDS)
        self.neg_set = set(NEGATIVE_KEYWORDS)

    def score_headline(self, headline: str) -> Tuple[str, float, float]:
        """
        Fast rule-assisted multi-keyword sentiment scoring (< 20ms).
        Returns: (sentiment, confidence_score, latency_ms)
        """
        t0 = time.perf_counter()
        words = set(re.findall(r'\w+', headline.lower()))

        pos_matches = len(words.intersection(self.pos_set))
        neg_matches = len(words.intersection(self.neg_set))

        if pos_matches > neg_matches:
            sentiment = "BULLISH"
            confidence = min(0.65 + (pos_matches * 0.12), 0.98)
        elif neg_matches > pos_matches:
            sentiment = "BEARISH"
            confidence = min(0.65 + (neg_matches * 0.12), 0.98)
        else:
            # Check context for general market questions
            if any(k in headline.lower() for k in ["will", "by", "before", "reach", "hit"]):
                sentiment = "BULLISH"
                confidence = 0.72 # Moderate baseline confidence for resolution markets
            else:
                sentiment = "NEUTRAL"
                confidence = 0.50

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return sentiment, confidence, round(latency_ms, 2)

    def evaluate_probability_skew(self, outcome_prices: List[str]) -> Tuple[str, float]:
        """
        Evaluates market odds probability skew from outcomePrices (e.g. ["0.88", "0.12"])
        Returns: (skew_direction, skew_confidence)
        """
        if not outcome_prices or len(outcome_prices) < 2:
            return "NEUTRAL", 0.50

        try:
            p0 = float(outcome_prices[0]) # YES price
            p1 = float(outcome_prices[1]) # NO price

            if p0 >= 0.70:
                return "HIGH_PROBABILITY_YES", p0
            elif p1 >= 0.70:
                return "HIGH_PROBABILITY_NO", p1
            else:
                return "BALANCED", max(p0, p1)
        except (ValueError, TypeError):
            return "NEUTRAL", 0.50

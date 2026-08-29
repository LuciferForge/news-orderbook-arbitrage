#!/usr/bin/env python3
"""
Sub-200ms Fast Sentiment Scorer
Parses incoming headlines and scores financial sentiment in under 20ms.
"""

import time
import re
from typing import Dict, Any, Tuple

POSITIVE_KEYWORDS = ["wins", "passed", "approved", "surges", "leading", "victory", "breakthrough"]
NEGATIVE_KEYWORDS = ["loses", "rejected", "failed", "drops", "behind", "defeat", "lawsuit"]

class FastSentimentScorer:
    def __init__(self):
        pass

    def score_headline(self, headline: str) -> Tuple[str, float, float]:
        """
        Fast rule-assisted sentiment scoring (< 20ms).
        Returns: (sentiment, confidence_score, latency_ms)
        """
        t0 = time.perf_counter()
        words = set(re.findall(r'\w+', headline.lower()))

        pos_count = len(words.intersection(set(POSITIVE_KEYWORDS)))
        neg_count = len(words.intersection(set(NEGATIVE_KEYWORDS)))

        if pos_count > neg_count:
            sentiment = "BULLISH"
            confidence = min(0.60 + (pos_count * 0.15), 0.98)
        elif neg_count > pos_count:
            sentiment = "BEARISH"
            confidence = min(0.60 + (neg_count * 0.15), 0.98)
        else:
            sentiment = "NEUTRAL"
            confidence = 0.50

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return sentiment, confidence, round(latency_ms, 2)

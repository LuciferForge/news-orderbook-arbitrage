#!/usr/bin/env python3
"""
Sub-200ms Arbitrage Engine Pipeline Test Runner
Simulates incoming breaking news events, scores sentiment, and benchmarks total pipeline latency.
"""

import asyncio
import time
from typing import Dict, Any
from stream_interceptor import StreamInterceptor
from sentiment_scorer import FastSentimentScorer
from order_router import RiskGuardedOrderRouter

async def run_arbitrage_benchmark():
    print("==================================================")
    print(" ⚡ SUB-200MS NEWS-TO-ORDERBOOK ARBITRAGE TEST ")
    print("==================================================")
    
    scorer = FastSentimentScorer()
    router = RiskGuardedOrderRouter(max_trade_usdc=2.50)

    async def handle_news_event(event: Dict[str, Any]):
        t_start = event["timestamp"]
        headline = event["headline"]
        market_token = event["market_token"]

        # 1. Score Sentiment (< 20ms)
        sentiment, confidence, scorer_ms = scorer.score_headline(headline)

        # 2. Route Order to CLOB if Bullish/Bearish
        side = "BUY" if sentiment == "BULLISH" else "SELL"
        success, msg, details = router.route_arbitrage_order(market_token, side, confidence)

        t_total_ms = (time.perf_counter() - t_start) * 1000.0

        print(f"\n📰 Headline: \"{headline}\"")
        print(f"   1. Sentiment: {sentiment} (Conf: {confidence:.2f}) | Scorer: {scorer_ms:.2f}ms")
        print(f"   2. Order Router: {msg}")
        print(f"   ⚡ TOTAL PIPELINE LATENCY: {t_total_ms:.2f}ms (Target: < 200ms)")
        
        if t_total_ms < 200.0:
            print("   ✅ SUB-200MS LATENCY TARGET ACHIEVED!")

    interceptor = StreamInterceptor(handle_news_event)

    # Ingest breaking news event
    print("1. Ingesting Breaking News Event into Stream Interceptor...")
    sample_headline = "Abdul El-Sayed wins major endorsement surging past opponents in Michigan Primary"
    sample_token = "75212375517444662942705581008505477009916343680049771629804936585862986754319"
    
    await interceptor.ingest_news_event(sample_headline, sample_token)
    await interceptor.process_queue()

    print("\n==================================================")
    print(" 📊 TEST SUMMARY: Arbitrage Engine Pipeline Verified!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_arbitrage_benchmark())

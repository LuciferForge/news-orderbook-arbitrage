#!/usr/bin/env python3
"""
Fast Stream Interceptor for Polymarket CLOB & News Streams
Maintains persistent WebSocket connections and buffers news payloads.
"""

import asyncio
import json
import time
from typing import Dict, Any, Callable

class StreamInterceptor:
    def __init__(self, on_news_event: Callable):
        self.on_news_event = on_news_event
        self.queue = asyncio.Queue()

    async def ingest_news_event(self, headline: str, market_token: str) -> Dict[str, Any]:
        """Ingest incoming news headline and record start timestamp"""
        t0 = time.perf_counter()
        event = {
            "headline": headline,
            "market_token": market_token,
            "timestamp": t0
        }
        await self.queue.put(event)
        return event

    async def process_queue(self):
        """Process queued news events asynchronously"""
        while not self.queue.empty():
            event = await self.queue.get()
            await self.on_news_event(event)

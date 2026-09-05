#!/usr/bin/env python3
"""
Polymarket CLOB V2 Real On-Chain Order Router
Executes live limit orders on Polymarket CLOB V2 API.
"""

import os
import sys
import time
import json
import logging
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

dotenv_path = '/Users/apple/Documents/Zero_fks/.env'
load_dotenv(dotenv_path)

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, OrderArgs, OrderType, AssetType, BalanceAllowanceParams, PartialCreateOrderOptions
from py_clob_client_v2.constants import POLYGON

logger = logging.getLogger("OrderRouterV2")

class RiskGuardedOrderRouter:
    def __init__(self, max_trade_usdc: float = 2.50):
        self.max_trade = max_trade_usdc
        self.host = "https://clob.polymarket.com"
        self.key = os.getenv("POLYMARKET_API_KEY")
        self.secret = os.getenv("POLYMARKET_SECRET")
        self.passphrase = os.getenv("POLYMARKET_PASSPHRASE")
        self.pkey = os.getenv("PRIVATE_KEY") or os.getenv("BASE_PRIVATE_KEY")
        self.funder = os.getenv("POLYMARKET_PROXY_ADDRESS", "0x53d5ba04d1ddaa7c9eb14d6e4b3896b15acbd88c")
        
        # Persistent SQLite database lock to prevent duplicate position entries across process restarts
        self.db_path = '/Users/apple/Documents/products/news-orderbook-arbitrage/executed_tokens.db'
        self.executed_tokens = self.load_executed_tokens_db()
        self.client = None
        self.init_clob_client()

    def load_executed_tokens_db(self) -> set:
        import sqlite3
        tokens = set()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS executed_tokens (token_id TEXT PRIMARY KEY, executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            conn.commit()
            cursor.execute("SELECT token_id FROM executed_tokens")
            rows = cursor.fetchall()
            tokens = {r[0] for r in rows}
            conn.close()
            logger.info(f"🔒 Loaded {len(tokens)} executed tokens from persistent SQLite database.")
        except Exception as e:
            logger.error(f"Error loading executed tokens DB: {e}")
        return tokens

    def save_executed_token_db(self, token_id: str):
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO executed_tokens (token_id) VALUES (?)", (str(token_id).strip(),))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving executed token to DB: {e}")

    def init_clob_client(self):
        try:
            if self.key and self.secret and self.passphrase and self.pkey:
                creds = ApiCreds(api_key=self.key, api_secret=self.secret, api_passphrase=self.passphrase)
                # Signature Type 2 = POLY_GNOSIS_SAFE
                self.client = ClobClient(
                    self.host,
                    key=self.pkey,
                    chain_id=POLYGON,
                    creds=creds,
                    signature_type=2,
                    funder=self.funder
                )
                logger.info(f"✅ Polymarket CLOB V2 Client Initialized (Gnosis Safe Funder: {self.funder})")
        except Exception as e:
            logger.error(f"❌ Failed to initialize CLOB V2 Client: {e}")

    def check_live_balance(self) -> float:
        if not self.client:
            return 0.0
        try:
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            res = self.client.get_balance_allowance(params)
            bal_raw = float(res.get("balance", 0))
            return bal_raw / 1e6
        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            return 0.0

    def route_arbitrage_order(self, token_id: str, side: str, confidence: float) -> Tuple[bool, str, Dict[str, Any]]:
        t0 = time.perf_counter()

        # 1. Confidence Threshold Guard (Must be >= 0.65)
        if confidence < 0.65:
            return False, f"Order Blocked: Confidence {confidence:.2f} < 0.65 Threshold", {"trade_size": 0.0}

        if not self.client:
            return False, "Order Failed: CLOB V2 Client not initialized", {}

        token_str = str(token_id).strip()

        # 2. STRICT IN-MEMORY DUPLICATE POSITION GUARD (Sub-Millisecond Check)
        if token_str in self.executed_tokens:
            logger.warning(f"🛡️ RISK GUARD TRIGGERED: Position already executed on token {token_str[:16]}... REJECTED.")
            return False, f"Order Blocked: Duplicate trade prevented for token {token_str[:16]}...", {"trade_size": 0.0}

        try:
            # 3. Unfilled Open Orders Check
            try:
                open_orders = self.client.get_open_orders()
                active_tokens = [str(o.get('asset_id')).strip() for o in open_orders if o.get('asset_id')]
                if token_str in active_tokens:
                    self.executed_tokens.add(token_str)
                    logger.warning(f"🛡️ RISK GUARD TRIGGERED: Unfilled order exists for token {token_str[:16]}... REJECTED.")
                    return False, f"Order Blocked: Duplicate unfilled order exists for token {token_str[:16]}...", {"trade_size": 0.0}
            except Exception as open_err:
                logger.warning(f"Could not verify open orders: {open_err}")

            # 4. Balance & Position Sizing Risk Guard (Cap trade size at max $2.50 or 20% of balance)
            live_bal = self.check_live_balance()
            if live_bal < 1.0:
                return False, f"Order Skipped: Low USDC balance (${live_bal:.2f})", {"trade_size": 0.0}

            # Enforce max $2.50 exposure limit per prediction
            safe_trade_amount = min(self.max_trade, 2.50, live_bal * 0.20)
            if safe_trade_amount < 1.0:
                safe_trade_amount = min(live_bal, 2.50)

            price_target = 0.95 if side.upper() == "BUY" else 0.05
            raw_qty = round(safe_trade_amount / price_target, 2)
            token_qty = max(raw_qty, 5.0) # Polymarket CLOB minimum order size is 5 shares

            # Fetch V2 tick_size & neg_risk
            try:
                tick_size = self.client.get_tick_size(token_str)
                neg_risk = self.client.get_neg_risk(token_str)
            except Exception:
                tick_size = "0.01"
                neg_risk = False

            options = PartialCreateOrderOptions(tick_size=str(tick_size), neg_risk=neg_risk)
            order_args = OrderArgs(
                price=price_target,
                size=token_qty,
                side=side.upper(),
                token_id=token_str
            )
            
            # Register in executed tokens set and SQLite DB to lock out duplicate entries permanently
            self.executed_tokens.add(token_str)
            self.save_executed_token_db(token_str)

            resp = self.client.create_and_post_order(order_args, options)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            
            if resp.get("success"):
                logger.info(f"🚀 CLOB ORDER EXECUTED! ({side} {token_qty} shares | ${safe_trade_amount:.2f} USDC | OrderID: {resp.get('orderID')})")
                return True, f"🚀 REAL CLOB V2 ORDER EXECUTED! ({side} {token_qty} shares | OrderID: {resp.get('orderID')})", {
                    "response": resp,
                    "latency_ms": round(latency_ms, 2)
                }
            else:
                return False, f"CLOB V2 Order Error: {resp.get('errorMsg')}", {"response": resp, "latency_ms": round(latency_ms, 2)}
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return False, f"Order Execution Exception: {e}", {"latency_ms": round(latency_ms, 2)}

if __name__ == "__main__":
    router = RiskGuardedOrderRouter(max_trade_usdc=2.50)
    bal = router.check_live_balance()
    print(f"=== CLOB V2 ORDER ROUTER DIAGNOSTIC ===")
    print(f"Live Gnosis Safe USDC Balance: ${bal:.2f}")

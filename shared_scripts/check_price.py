#!/usr/bin/env python3
"""
Quick price fetcher for the Go scheduler.
Fetches current prices for given symbols.

Usage: python3 check_price.py BTC/USDT SOL/USDT

Routing:
- pair symbols (e.g. BTC/USDT) are fetched via BinanceUS
- bare spot coins (e.g. BTC) are fetched via OKX
"""

import json
import sys
import traceback


_EXCHANGES = {}
_TICKERS = {}


def _exchange(name):
    if name not in _EXCHANGES:
        import ccxt
        _EXCHANGES[name] = getattr(ccxt, name)({"enableRateLimit": True})
    return _EXCHANGES[name]


def _tickers(name):
    if name not in _TICKERS:
        exchange = _exchange(name)
        try:
            _TICKERS[name] = exchange.fetch_tickers()
        except Exception:
            _TICKERS[name] = None
    return _TICKERS[name]


def _last_price(ticker):
    if not isinstance(ticker, dict):
        return 0.0
    last = ticker.get("last") or 0
    try:
        return float(last)
    except (TypeError, ValueError):
        return 0.0


def _fetch_binanceus(symbol):
    tickers = _tickers("binanceus") or {}
    ticker = tickers.get(symbol)
    if ticker:
        price = _last_price(ticker)
        if price > 0:
            return price
    ticker = _exchange("binanceus").fetch_ticker(symbol)
    return _last_price(ticker)


def _fetch_okx_spot(symbol):
    tickers = _tickers("okx") or {}
    for suffix in ("/USDT", "/USD", "/USDC"):
        ticker = tickers.get(symbol + suffix)
        if ticker:
            price = _last_price(ticker)
            if price > 0:
                return price
    exchange = _exchange("okx")
    for suffix in ("/USDT", "/USD", "/USDC"):
        try:
            ticker = exchange.fetch_ticker(symbol + suffix)
            price = _last_price(ticker)
            if price > 0:
                return price
        except Exception:
            continue
    return 0.0


def fetch_price(symbol):
    # Preserve the original symbol as the JSON key.
    if "/" in symbol:
        try:
            price = _fetch_binanceus(symbol)
            if price > 0:
                return price
        except Exception:
            pass
        try:
            return _fetch_okx_spot(symbol.split("/", 1)[0])
        except Exception:
            return 0.0

    try:
        price = _fetch_okx_spot(symbol)
        if price > 0:
            return price
    except Exception:
        pass

    try:
        return _fetch_binanceus(symbol)
    except Exception:
        return 0.0


def main():
    symbols = sys.argv[1:]
    if not symbols:
        print(json.dumps({}))
        return

    prices = {}
    for symbol in symbols:
        try:
            price = fetch_price(symbol)
            if price > 0:
                prices[symbol] = round(price, 2)
            else:
                print(f"Failed to fetch {symbol}: no positive price", file=sys.stderr)
        except Exception as e:
            print(f"Failed to fetch {symbol}: {e}", file=sys.stderr)

    missing = [s for s in symbols if s not in prices]
    if missing:
        try:
            import os as _os2
            sys.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), "..", "platforms", "blofin"))
            from spot_adapter import BloFinSpotExchangeAdapter
            tickers = {x.get("instId"): x for x in BloFinSpotExchangeAdapter().get_spot_tickers()}
            for symbol in missing:
                base = (symbol or "").split("/")[0].split("-")[0].strip().upper()
                tk = tickers.get(base + "-USDT", {})
                try:
                    last = float(tk.get("last", 0) or 0)
                except (ValueError, TypeError):
                    last = 0
                if last > 0:
                    prices[symbol] = round(last, 2)
        except Exception as e2:
            print(f"BloFin spot fallback failed: {e2}", file=sys.stderr)

    print(json.dumps(prices))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({}))
        sys.exit(1)

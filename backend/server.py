"""
YUZARE Real-Time Trading Terminal Server
FastAPI Web & WebSocket Server
"""

import os
import sys
import time
import json
import asyncio
import logging
import random
import string
from typing import Dict, Any, List, Optional

# Pastikan root directory terdaftar di sys.path agar import selalu berhasil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import websockets

from backend.indicators import YUZARE_Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("YUZARE")

app = FastAPI(title="YUZARE Trading Terminal", version="1.0.0")

# Enable CORS for any client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = YUZARE_Engine()

# Pair mapping dengan offset kalibrasi default untuk menyesuaikan dengan broker MT5
PAIR_MAP = {
    "XAUUSD": {"binance": "PAXGUSDT", "tv_symbol": "OANDA:XAUUSD", "name": "Emas / Dollar A.S. (XAUUSD · OANDA)", "type": "Metals", "digits": 2, "pip": 0.1, "default_offset": 0.0},
    "BTCUSD": {"binance": "BTCUSDT", "name": "Bitcoin / Tether", "type": "Crypto", "digits": 2, "pip": 1.0, "default_offset": 0.0},
    "ETHUSD": {"binance": "ETHUSDT", "name": "Ethereum / Tether", "type": "Crypto", "digits": 2, "pip": 0.1, "default_offset": 0.0},
    "SOLUSD": {"binance": "SOLUSDT", "name": "Solana / Tether", "type": "Crypto", "digits": 2, "pip": 0.01, "default_offset": 0.0},
    "EURUSD": {"binance": "EURUSDT", "name": "Euro / US Dollar", "type": "Forex", "digits": 4, "pip": 0.0001, "default_offset": 0.0},
    "GBPUSD": {"binance": "GBPUSDT", "name": "British Pound / US Dollar", "type": "Forex", "digits": 4, "pip": 0.0001, "default_offset": 0.0},
}

TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]

# Global configurable offsets
broker_offsets: Dict[str, float] = {k: float(v.get("default_offset", 0.0)) for k, v in PAIR_MAP.items()}

# Default candle limits per timeframe untuk menampilkan riwayat berhari-hari sebelumnya
DEFAULT_TF_LIMITS = {
    "1m": 2500,   # ~42 jam (hampir 2 hari penuh)
    "5m": 1500,   # ~5.2 hari (1 minggu trading penuh)
    "15m": 1200,  # ~12.5 hari (2 minggu trading)
    "30m": 1000,  # ~20.8 hari (hampir 1 bulan)
    "1h": 1000,   # ~41.6 hari (> 1 bulan)
    "4h": 800,    # ~133 hari (> 4 bulan)
    "1d": 600,    # ~600 hari (> 1.5 tahun)
    "1w": 400,    # ~400 minggu (> 7.5 tahun)
}

def fetch_binance_klines(symbol: str, interval: str, limit: int = 2500, offset: float = 0.0) -> List[Dict[str, Any]]:
    """Fetch candlestick data from Binance Vision API dengan multi-batch pagination untuk menampilkan riwayat hari-hari sebelumnya"""
    binance_symbol = str(PAIR_MAP.get(symbol, {}).get("binance", "PAXGUSDT"))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    raw = []
    needed = limit
    end_time = None

    # Ambil hingga 3 batch (maksimal 3000 candle) untuk mencakup 2+ hari riwayat
    max_batches = 3 if limit > 1000 else 1
    for _ in range(max_batches):
        if needed <= 0:
            break
        batch_size = min(needed, 1000)
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={binance_symbol}&interval={interval}&limit={batch_size}"
        if end_time:
            url += f"&endTime={end_time}"
        try:
            resp = requests.get(url, timeout=7, headers=headers)
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not isinstance(batch, list) or not batch:
                break
            if not raw:
                raw = batch
            else:
                raw = batch + raw
            end_time = int(batch[0][0]) - 1
            needed -= len(batch)
            if len(batch) < batch_size:
                break
        except Exception as e:
            logger.error(f"Error fetching klines batch: {e}")
            break

    if not raw:
        return []

    candles = []
    total_items = len(raw)
    for idx, item in enumerate(raw):
        # [open_time, open, high, low, close, volume, close_time, ...]
        t = int(item[0] // 1000) # seconds for Lightweight Charts
        o = round(float(item[1]) + offset, 2)
        h = round(float(item[2]) + offset, 2)
        l = round(float(item[3]) + offset, 2)
        c = round(float(item[4]) + offset, 2)
        v = float(item[5])

        # Hilangkan bar dummy datar (high == low / 0 movement) pada 1m agar chart mulus seperti MT5
        if interval == "1m" and idx < total_items - 1 and h <= l:
            continue

        candles.append({
            "time": t,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v
        })
    return candles[-limit:]

def prepend_tv_header(st: str) -> str:
    return f"~m~{len(st)}~m~{st}"

def construct_tv_msg(func: str, args: list) -> str:
    return prepend_tv_header(json.dumps({"m": func, "p": args}))

def generate_tv_session() -> str:
    return "cs_" + "".join(random.choices(string.ascii_letters + string.digits, k=12))

async def async_fetch_tv_klines(symbol: str = "OANDA:XAUUSD", interval: str = "1m", limit: int = 2500) -> List[Dict[str, Any]]:
    """Mengambil candlestick asli langsung dari TradingView WebSocket (OANDA:XAUUSD)"""
    tf_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "D", "1w": "W"}
    res_itv = tf_map.get(interval, "1")
    uri = "wss://data.tradingview.com/socket.io/websocket"
    headers = {"Origin": "https://www.tradingview.com", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        async with websockets.connect(uri, additional_headers=headers, close_timeout=4, ping_timeout=6) as ws:
            await ws.recv()
            cs = generate_tv_session()
            await ws.send(construct_tv_msg("set_auth_token", ["unauthorized_user_token"]))
            await ws.send(construct_tv_msg("chart_create_session", [cs, ""]))
            sym_spec = json.dumps({"symbol": symbol, "adjustment": "splits"})
            await ws.send(construct_tv_msg("resolve_symbol", [cs, "sds_sym_1", "=" + sym_spec]))
            await ws.send(construct_tv_msg("create_series", [cs, "sds_1", "s1", "sds_sym_1", res_itv, limit]))

            for _ in range(20):
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                raw_str = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
                if "timescale_update" in raw_str:
                    parts = raw_str.split("~m~")
                    for p in parts:
                        if p.startswith("{"):
                            d = json.loads(p)
                            if d.get("m") == "timescale_update":
                                series = d.get("p", [None, {}])[1].get("sds_1", {}).get("s", [])
                                candles = []
                                for row in series:
                                    val = row["v"]
                                    candles.append({
                                        "time": int(val[0]),
                                        "open": round(float(val[1]), 2),
                                        "high": round(float(val[2]), 2),
                                        "low": round(float(val[3]), 2),
                                        "close": round(float(val[4]), 2),
                                        "volume": round(float(val[5]), 2)
                                    })
                                if candles:
                                    return candles
    except Exception as e:
        logger.warning(f"TradingView WS fetch error for {symbol}: {e}")
    return []

def fetch_tradingview_klines(symbol: str = "OANDA:XAUUSD", interval: str = "1m", limit: int = 2500) -> List[Dict[str, Any]]:
    try:
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(async_fetch_tv_klines(symbol, interval, limit))
        loop.close()
        return res
    except Exception as e:
        logger.warning(f"TradingView sync wrapper error: {e}")
        return []

def fetch_market_klines(symbol: str, interval: str, limit: int = 2500, offset: float = 0.0) -> List[Dict[str, Any]]:
    """Mengambil candlestick OANDA (XAUUSD) dari TradingView atau fallback Binance Vision"""
    pair_cfg = PAIR_MAP.get(symbol, {})
    tv_symbol = pair_cfg.get("tv_symbol")
    if tv_symbol:
        tv_candles = fetch_tradingview_klines(str(tv_symbol), interval, limit)
        if tv_candles and len(tv_candles) >= 20:
            digits: int = int(pair_cfg.get("digits", 2))
            if offset != 0.0:
                for c in tv_candles:
                    c["open"] = round(c["open"] + offset, digits)
                    c["high"] = round(c["high"] + offset, digits)
                    c["low"] = round(c["low"] + offset, digits)
                    c["close"] = round(c["close"] + offset, digits)
            else:
                for c in tv_candles:
                    c["open"] = round(c["open"], digits)
                    c["high"] = round(c["high"], digits)
                    c["low"] = round(c["low"], digits)
                    c["close"] = round(c["close"], digits)
            return tv_candles
    return fetch_binance_klines(symbol, interval, limit, offset)

@app.get("/api/pairs")
def get_pairs():
    """Daftar pair yang didukung"""
    return {
        "pairs": [
            {"symbol": k, "name": v["name"], "type": v["type"], "digits": v["digits"], "offset": broker_offsets.get(k, 0.0)}
            for k, v in PAIR_MAP.items()
        ],
        "timeframes": TIMEFRAMES,
        "offsets": broker_offsets
    }

@app.post("/api/offset")
def update_offset(symbol: str = Query("XAUUSD"), offset: float = Query(8.0)):
    """Memperbarui kalibrasi offset broker MT5 untuk pair tertentu"""
    symbol = symbol.upper()
    if symbol in PAIR_MAP:
        broker_offsets[symbol] = round(offset, 2)
        return {"status": "ok", "symbol": symbol, "offset": broker_offsets[symbol]}
    return JSONResponse(status_code=400, content={"error": "Symbol not found"})

@app.get("/api/analysis")
def get_analysis(
    symbol: str = Query("XAUUSD", description="Symbol e.g. XAUUSD, BTCUSD"),
    timeframe: str = Query("1m", description="Timeframe e.g. 1m, 5m, 1h, 1d"),
    limit: Optional[int] = Query(None, ge=50, le=5000),
    sl_pips: float = Query(30.0, description="Stop Loss in pips"),
    tp_targets: Optional[str] = Query(None, description="Comma-separated TP pips e.g. 30,50,70,100"),
    tp1_pips: float = Query(30.0, description="TP1 in pips"),
    tp2_pips: float = Query(50.0, description="TP2 in pips"),
    tp3_pips: float = Query(70.0, description="TP3 in pips"),
    tp4_pips: float = Query(100.0, description="TP4 in pips"),
    rr_tp1: Optional[float] = Query(None),
    rr_tp2: Optional[float] = Query(None),
    rr_tp3: Optional[float] = Query(None),
):
    """
    Mengambil data candlestick dan menjalankan YUZARE Indicator Engine.
    Menghasilkan candle colored, buy/sell zero-repaint signals, pending zones, dan dual signal levels.
    """
    symbol = str(symbol.default if hasattr(symbol, 'default') else symbol).upper()
    timeframe = str(timeframe.default if hasattr(timeframe, 'default') else timeframe)
    raw_lim = limit.default if hasattr(limit, 'default') else limit
    if raw_lim is None or raw_lim == 250:
        limit = DEFAULT_TF_LIMITS.get(timeframe, 2000)
    else:
        limit = int(raw_lim)
    sl_pips = float(sl_pips.default if hasattr(sl_pips, 'default') else sl_pips)
    tp1_pips = float(tp1_pips.default if hasattr(tp1_pips, 'default') else tp1_pips)
    tp2_pips = float(tp2_pips.default if hasattr(tp2_pips, 'default') else tp2_pips)
    tp3_pips = float(tp3_pips.default if hasattr(tp3_pips, 'default') else tp3_pips)
    tp4_pips = float(tp4_pips.default if hasattr(tp4_pips, 'default') else tp4_pips)

    if symbol not in PAIR_MAP:
        symbol = "XAUUSD"
    if timeframe not in TIMEFRAMES:
        timeframe = "1m"

    offset = broker_offsets.get(symbol, 0.0)
    candles = fetch_market_klines(symbol, timeframe, limit, offset=offset)
    if not candles:
        return JSONResponse(status_code=502, content={"error": "Failed to fetch market data"})

    if tp_targets:
        try:
            tp_list = [float(x.strip()) for x in tp_targets.split(",") if x.strip()]
        except Exception:
            tp_list = [tp1_pips, tp2_pips, tp3_pips, tp4_pips]
    else:
        tp_list = [tp1_pips, tp2_pips, tp3_pips, tp4_pips]

    pip_unit: float = float(PAIR_MAP.get(symbol, {}).get("pip", 0.1))
    result = engine.analyze(
        candles, 
        sl_pips=sl_pips, 
        tp_list=tp_list,
        tp1_pips=tp1_pips, 
        tp2_pips=tp2_pips, 
        tp3_pips=tp3_pips, 
        tp4_pips=tp4_pips,
        pip_unit=pip_unit
    )
    result["symbol"] = symbol
    result["timeframe"] = timeframe
    result["pair_info"] = PAIR_MAP[symbol]
    result["offset"] = offset
    
    return result

@app.get("/api/stats/all")
def get_all_stats(
    symbol: str = "XAUUSD",
    sl_pips: float = 30.0,
    tp_targets: Optional[str] = None,
    tp1_pips: float = 30.0,
    tp2_pips: float = 50.0,
    tp3_pips: float = 70.0,
    tp4_pips: float = 100.0,
):
    """
    Menghitung statistik performa kumulatif dari seluruh timeframe (1M sampai 1W).
    """
    symbol = str(symbol.default if hasattr(symbol, 'default') else symbol).upper()
    sl_pips = float(sl_pips.default if hasattr(sl_pips, 'default') else sl_pips)
    tp1_pips = float(tp1_pips.default if hasattr(tp1_pips, 'default') else tp1_pips)
    tp2_pips = float(tp2_pips.default if hasattr(tp2_pips, 'default') else tp2_pips)
    tp3_pips = float(tp3_pips.default if hasattr(tp3_pips, 'default') else tp3_pips)
    tp4_pips = float(tp4_pips.default if hasattr(tp4_pips, 'default') else tp4_pips)

    if symbol not in PAIR_MAP:
        symbol = "XAUUSD"
    offset = broker_offsets.get(symbol, 0.0)

    if tp_targets:
        try:
            tp_list = [float(x.strip()) for x in tp_targets.split(",") if x.strip()]
        except Exception:
            tp_list = [tp1_pips, tp2_pips, tp3_pips, tp4_pips]
    else:
        tp_list = [tp1_pips, tp2_pips, tp3_pips, tp4_pips]

    by_tf = {}
    tot_signals = 0
    tot_tp = 0
    tot_sl = 0

    pip_unit: float = float(PAIR_MAP.get(symbol, {}).get("pip", 0.1))
    for tf in TIMEFRAMES:
        tf_limit = DEFAULT_TF_LIMITS.get(tf, 1000)
        candles = fetch_market_klines(symbol, tf, limit=tf_limit, offset=offset)
        if candles:
            res = engine.analyze(candles, sl_pips=sl_pips, tp_list=tp_list, pip_unit=pip_unit)
            st = res.get("stats", {})
            by_tf[tf] = st
            tot_signals += st.get("total_signals", 0)
            tot_tp += st.get("tp_hits", 0)
            tot_sl += st.get("sl_hits", 0)

    decided = tot_tp + tot_sl
    win_rate = round((tot_tp / decided * 100.0), 1) if decided > 0 else 0.0

    return {
        "symbol": symbol,
        "combined": {
            "total_signals": tot_signals,
            "tp_hits": tot_tp,
            "sl_hits": tot_sl,
            "completed_trades": decided,
            "win_rate": win_rate
        },
        "by_timeframe": by_tf
    }

# Active WebSocket connections for live client broadcast
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

@app.get("/api/ticker")
def get_ticker(symbol: str = Query("XAUUSD")):
    """Mengambil harga ticker terkini secara cepat dengan offset MT5"""
    symbol = symbol.upper()
    binance_symbol = str(PAIR_MAP.get(symbol, {}).get("binance", "PAXGUSDT"))
    offset = float(broker_offsets.get(symbol, 0.0))
    url = f"https://data-api.binance.vision/api/v3/ticker/price?symbol={binance_symbol}"
    try:
        resp = requests.get(url, timeout=3, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return {
                "symbol": symbol,
                "price": round(float(resp.json()["price"]) + offset, 2),
                "offset": offset,
                "time": int(time.time())
            }
    except Exception as e:
        logger.warning(f"Error fetching ticker: {e}")
    return {"symbol": symbol, "price": 0.0, "offset": offset, "time": int(time.time())}

@app.post("/api/mt5_tick")
async def receive_mt5_tick(tick: Dict[str, Any]):
    """Menerima tick langsung dari MetaTrader 5 (MT5 EA Bridge)"""
    sym = str(tick.get("symbol", "XAUUSD")).upper()
    bid = float(tick.get("bid", 0))
    ask = float(tick.get("ask", 0))
    if bid > 0:
        await manager.broadcast(json.dumps({
            "type": "ticker",
            "symbol": sym,
            "price": bid,
            "ask": ask,
            "source": "MT5_DIRECT",
            "time": int(time.time())
        }))
    return {"status": "ok"}

@app.websocket("/ws/live/{symbol}/{timeframe}")
async def websocket_live_stream(websocket: WebSocket, symbol: str, timeframe: str):
    """
    WebSocket streaming real-time candlestick update & tick data langsung ke browser.
    Menggabungkan kline dan ticker stream untuk pergerakan real-time kontinu setiap detik!
    """
    await manager.connect(websocket)
    symbol = symbol.upper()
    binance_symbol = str(PAIR_MAP.get(symbol, {}).get("binance", "PAXGUSDT")).lower()
    # Menggunakan combined stream kline + aggTrade (0ms delay) + bookTicker agar chart bergerak instan secepat MT5!
    ws_url = f"wss://data-stream.binance.vision/stream?streams={binance_symbol}@kline_{timeframe}/{binance_symbol}@aggTrade/{binance_symbol}@bookTicker"

    logger.info(f"Client connected for {symbol} {timeframe}. Connecting to Binance Combined WS: {ws_url}")
    
    # Send instant connection acknowledgment
    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "symbol": symbol,
            "timeframe": timeframe,
            "offset": broker_offsets.get(symbol, 0.0),
            "status": "ready"
        }))
    except Exception:
        pass

    running = True

    async def listen_tradingview():
        nonlocal running
        tf_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "D", "1w": "W"}
        res_itv = tf_map.get(timeframe, "1")
        tv_sym = str(PAIR_MAP.get(symbol, {}).get("tv_symbol", "OANDA:XAUUSD"))
        digits: int = int(PAIR_MAP.get(symbol, {}).get("digits", 2))
        uri = "wss://data.tradingview.com/socket.io/websocket"
        headers = {"Origin": "https://www.tradingview.com", "User-Agent": "Mozilla/5.0"}
        while running:
            try:
                async with websockets.connect(uri, additional_headers=headers) as tws:
                    await tws.recv()
                    cs = generate_tv_session()
                    await tws.send(construct_tv_msg("set_auth_token", ["unauthorized_user_token"]))
                    await tws.send(construct_tv_msg("chart_create_session", [cs, ""]))
                    sym_spec = json.dumps({"symbol": tv_sym, "adjustment": "splits"})
                    await tws.send(construct_tv_msg("resolve_symbol", [cs, "sds_sym_1", "=" + sym_spec]))
                    await tws.send(construct_tv_msg("create_series", [cs, "sds_1", "s1", "sds_sym_1", res_itv, 10]))
                    while running:
                        msg = await tws.recv()
                        msg_str: str = msg.decode("utf-8", errors="ignore") if isinstance(msg, bytes) else str(msg)
                        cur_offset: float = float(broker_offsets.get(symbol, 0.0))
                        if "du" in msg_str or "timescale_update" in msg_str:
                            parts = msg_str.split("~m~")
                            for p in parts:
                                if p.startswith("{"):
                                    d = json.loads(p)
                                    s_data = d.get("p", [None, {}])[1].get("sds_1", {}).get("s", [])
                                    if s_data:
                                        last_bar = s_data[-1]["v"]
                                        t_bar = int(last_bar[0])
                                        o_bar = round(float(last_bar[1]) + cur_offset, digits)
                                        h_bar = round(float(last_bar[2]) + cur_offset, digits)
                                        l_bar = round(float(last_bar[3]) + cur_offset, digits)
                                        c_bar = round(float(last_bar[4]) + cur_offset, digits)
                                        await websocket.send_text(json.dumps({
                                            "type": "kline",
                                            "symbol": symbol,
                                            "timeframe": timeframe,
                                            "time": t_bar,
                                            "open": o_bar,
                                            "high": h_bar,
                                            "low": l_bar,
                                            "close": c_bar,
                                            "volume": round(float(last_bar[5]), 2),
                                            "is_closed": False
                                        }))
                                        await websocket.send_text(json.dumps({
                                            "type": "ticker",
                                            "symbol": symbol,
                                            "price": c_bar,
                                            "time": int(time.time())
                                        }))
            except WebSocketDisconnect:
                running = False
                break
            except Exception as e:
                logger.warning(f"TradingView WS listen error: {e}. Reconnecting in 2s...")
                await asyncio.sleep(2)

    async def listen_binance():
        nonlocal running
        while running:
            try:
                async with websockets.connect(ws_url, ping_interval=20) as bws:
                    logger.info(f"Connected to Binance WS for {binance_symbol} {timeframe}")
                    while running:
                        msg = await bws.recv()
                        raw = json.loads(msg)
                        stream = raw.get("stream", "")
                        data = raw.get("data", {})
                        cur_offset = broker_offsets.get(symbol, 0.0)
                        
                        if "aggTrade" in stream:
                            cur_price = round(float(data.get("p", 0)) + cur_offset, 2)
                            await websocket.send_text(json.dumps({
                                "type": "ticker",
                                "symbol": symbol,
                                "price": cur_price,
                                "time": int(data.get("E", 0) // 1000)
                            }))
                        elif "bookTicker" in stream:
                            bid = round(float(data.get("b", 0)) + cur_offset, 2)
                            ask = round(float(data.get("a", 0)) + cur_offset, 2)
                            await websocket.send_text(json.dumps({
                                "type": "bookTicker",
                                "symbol": symbol,
                                "price": bid,
                                "bid": bid,
                                "ask": ask,
                                "spread": round(ask - bid, 2),
                                "time": int(time.time())
                            }))
                        elif "kline" in stream:
                            k = data.get("k", {})
                            if k:
                                candle_data = {
                                    "type": "kline",
                                    "symbol": symbol,
                                    "timeframe": timeframe,
                                    "time": int(k["t"] // 1000),
                                    "open": round(float(k["o"]) + cur_offset, 2),
                                    "high": round(float(k["h"]) + cur_offset, 2),
                                    "low": round(float(k["l"]) + cur_offset, 2),
                                    "close": round(float(k["c"]) + cur_offset, 2),
                                    "volume": float(k["v"]),
                                    "is_closed": k["x"] # True if bar closed (zero repaint trigger!)
                                }
                                await websocket.send_text(json.dumps(candle_data))
            except WebSocketDisconnect:
                running = False
                break
            except Exception as e:
                logger.warning(f"Binance WS connection error: {e}. Reconnecting in 2s...")
                await asyncio.sleep(2)

    has_tv = bool(PAIR_MAP.get(symbol, {}).get("tv_symbol"))
    stream_task = asyncio.create_task(listen_tradingview() if has_tv else listen_binance())

    try:
        while True:
            # Keep receiving client pings or instructions
            client_msg = await websocket.receive_text()
            if client_msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        running = False
        stream_task.cancel()
        manager.disconnect(websocket)
        logger.info(f"Client disconnected for {symbol}")
    except Exception as e:
        running = False
        stream_task.cancel()
        manager.disconnect(websocket)

AUTH_USERS = {
    "zakzakqy": "Savior,123",
    "piterxzakqy": "piterxzakqy123",
}

@app.post("/api/auth/login")
async def api_auth_login(payload: Dict[str, Any]):
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    
    if username in AUTH_USERS and AUTH_USERS[username] == password:
        return JSONResponse(status_code=200, content={
            "status": "ok",
            "username": username,
            "message": "Login berhasil"
        })
    return JSONResponse(status_code=401, content={
        "status": "error",
        "message": "Username atau password salah!"
    })

# Static file resolution helpers (Zero-Dependency & Serverless Safe)
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(root_dir, "frontend")

def read_static_text(filename: str) -> Optional[str]:
    candidates = [
        os.path.join(root_dir, filename),
        os.path.join(frontend_dir, filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(os.getcwd(), "frontend", filename),
        os.path.join(os.path.dirname(__file__), "..", filename),
        os.path.join(os.path.dirname(__file__), "..", "frontend", filename)
    ]
    for p in candidates:
        abs_p = os.path.abspath(p)
        if os.path.isfile(abs_p):
            try:
                with open(abs_p, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
    return None

def read_static_bytes(filename: str) -> Optional[bytes]:
    candidates = [
        os.path.join(root_dir, filename),
        os.path.join(frontend_dir, filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(os.getcwd(), "frontend", filename),
        os.path.join(os.path.dirname(__file__), "..", filename),
        os.path.join(os.path.dirname(__file__), "..", "frontend", filename)
    ]
    for p in candidates:
        abs_p = os.path.abspath(p)
        if os.path.isfile(abs_p):
            try:
                with open(abs_p, "rb") as f:
                    return f.read()
            except Exception:
                pass
    return None

@app.get("/")
def serve_index():
    content = read_static_text("index.html")
    if content:
        return HTMLResponse(content=content, status_code=200)
    return HTMLResponse(content="<h2>YUZARE Trading Terminal - Initializing...</h2>", status_code=200)

@app.get("/styles.css")
def serve_styles():
    content = read_static_text("styles.css")
    if content:
        return Response(content=content, media_type="text/css")
    return Response(content="/* CSS */", media_type="text/css")

@app.get("/app.js")
def serve_app_js():
    content = read_static_text("app.js")
    if content:
        return Response(content=content, media_type="application/javascript")
    return Response(content="// JS", media_type="application/javascript")

@app.get("/lightweight-charts.standalone.production.js")
def serve_charts_js():
    content = read_static_bytes("lightweight-charts.standalone.production.js")
    if content:
        return Response(content=content, media_type="application/javascript")
    return Response(content="// Chart library", media_type="application/javascript")

@app.get("/YUZARE_Indicator.pine")
def serve_pine_script():
    content = read_static_text("YUZARE_Indicator.pine")
    if content:
        return Response(content=content, media_type="text/plain")
    return Response(content="// YUZARE Pine Script", media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="127.0.0.1", port=8000, reload=True)

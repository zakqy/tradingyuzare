"""
YUZARE Real-Time Trading Terminal Server
FastAPI Web & WebSocket Server
"""

import os
import sys
import json
import asyncio
import logging
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
    "XAUUSD": {"binance": "PAXGUSDT", "name": "Gold Spot / U.S. Dollar", "type": "Metals", "digits": 2, "pip": 0.1, "default_offset": 8.0},
    "BTCUSD": {"binance": "BTCUSDT", "name": "Bitcoin / Tether", "type": "Crypto", "digits": 2, "pip": 1.0, "default_offset": 0.0},
    "ETHUSD": {"binance": "ETHUSDT", "name": "Ethereum / Tether", "type": "Crypto", "digits": 2, "pip": 0.1, "default_offset": 0.0},
    "SOLUSD": {"binance": "SOLUSDT", "name": "Solana / Tether", "type": "Crypto", "digits": 2, "pip": 0.01, "default_offset": 0.0},
    "EURUSD": {"binance": "EURUSDT", "name": "Euro / US Dollar", "type": "Forex", "digits": 4, "pip": 0.0001, "default_offset": 0.0},
    "GBPUSD": {"binance": "GBPUSDT", "name": "British Pound / US Dollar", "type": "Forex", "digits": 4, "pip": 0.0001, "default_offset": 0.0},
}

TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]

# Global configurable offsets
broker_offsets: Dict[str, float] = {k: v.get("default_offset", 0.0) for k, v in PAIR_MAP.items()}

def fetch_binance_klines(symbol: str, interval: str, limit: int = 300, offset: float = 0.0) -> List[Dict[str, Any]]:
    """Fetch candlestick data from Binance Vision API dengan kalibrasi offset MT5"""
    binance_symbol = PAIR_MAP.get(symbol, {}).get("binance", "PAXGUSDT")
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={binance_symbol}&interval={interval}&limit={limit}"
    
    try:
        resp = requests.get(url, timeout=7, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            raw = resp.json()
            candles = []
            for item in raw:
                # [open_time, open, high, low, close, volume, close_time, ...]
                t = int(item[0] // 1000) # seconds for Lightweight Charts
                candles.append({
                    "time": t,
                    "open": round(float(item[1]) + offset, 2),
                    "high": round(float(item[2]) + offset, 2),
                    "low": round(float(item[3]) + offset, 2),
                    "close": round(float(item[4]) + offset, 2),
                    "volume": float(item[5])
                })
            return candles
        else:
            logger.warning(f"Binance Vision returned status {resp.status_code}")
    except Exception as e:
        logger.error(f"Error fetching klines: {e}")
    
    return []

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
    limit: int = Query(250, ge=50, le=1000),
    sl_pips: float = Query(30.0, description="Stop Loss in pips"),
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
    symbol = symbol.upper()
    if symbol not in PAIR_MAP:
        symbol = "XAUUSD"
    if timeframe not in TIMEFRAMES:
        timeframe = "1m"

    offset = broker_offsets.get(symbol, 0.0)
    candles = fetch_binance_klines(symbol, timeframe, limit, offset=offset)
    if not candles:
        return JSONResponse(status_code=502, content={"error": "Failed to fetch market data"})

    result = engine.analyze(
        candles, 
        sl_pips=sl_pips, 
        tp1_pips=tp1_pips, 
        tp2_pips=tp2_pips, 
        tp3_pips=tp3_pips, 
        tp4_pips=tp4_pips
    )
    result["symbol"] = symbol
    result["timeframe"] = timeframe
    result["pair_info"] = PAIR_MAP[symbol]
    result["offset"] = offset
    
    return result

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
    import time
    symbol = symbol.upper()
    binance_symbol = PAIR_MAP.get(symbol, {}).get("binance", "PAXGUSDT")
    offset = broker_offsets.get(symbol, 0.0)
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
    import time
    sym = tick.get("symbol", "XAUUSD").upper()
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
    binance_symbol = PAIR_MAP.get(symbol, {}).get("binance", "PAXGUSDT").lower()
    # Menggunakan combined stream kline + ticker agar chart selalu bergerak setiap detik!
    ws_url = f"wss://data-stream.binance.vision/stream?streams={binance_symbol}@kline_{timeframe}/{binance_symbol}@ticker"

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
                        
                        if "kline" in stream:
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
                        elif "ticker" in stream:
                            ticker_data = {
                                "type": "ticker",
                                "symbol": symbol,
                                "price": round(float(data.get("c", 0)) + cur_offset, 2),
                                "high": round(float(data.get("h", 0)) + cur_offset, 2),
                                "low": round(float(data.get("l", 0)) + cur_offset, 2),
                                "time": int(data.get("E", 0) // 1000)
                            }
                            await websocket.send_text(json.dumps(ticker_data))
            except WebSocketDisconnect:
                running = False
                break
            except Exception as e:
                logger.warning(f"Binance WS connection error: {e}. Reconnecting in 2s...")
                await asyncio.sleep(2)

    binance_task = asyncio.create_task(listen_binance())

    try:
        while True:
            # Keep receiving client pings or instructions
            client_msg = await websocket.receive_text()
            if client_msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        running = False
        binance_task.cancel()
        manager.disconnect(websocket)
        logger.info(f"Client disconnected for {symbol}")
    except Exception as e:
        running = False
        binance_task.cancel()
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

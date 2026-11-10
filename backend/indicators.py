"""
YUZARE Indicator Engine
Algoritma Zero-Repaint, Dual Signal, Pending Zones, dan Level TP/SL Otomatis.
Dioptimalkan untuk XAUUSD (Gold Spot) dan BTCUSD (Bitcoin).
"""

from typing import List, Dict, Any, Optional
import math

def calculate_atr(candles: List[Dict[str, float]], period: int = 14) -> List[float]:
    """Menghitung Average True Range (ATR)"""
    if len(candles) < 2:
        return [0.0] * len(candles)
    
    tr_list = [candles[0]["high"] - candles[0]["low"]]
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_list.append(tr)
    
    atr = []
    if len(tr_list) >= period:
        first_atr = sum(tr_list[:period]) / period
        atr = [first_atr] * period
        for i in range(period, len(tr_list)):
            curr_atr = (atr[-1] * (period - 1) + tr_list[i]) / period
            atr.append(curr_atr)
    else:
        atr = tr_list
    return atr

def calculate_ema(values: List[float], period: int) -> List[float]:
    """Menghitung Exponential Moving Average (EMA)"""
    if not values:
        return []
    ema = []
    k = 2.0 / (period + 1)
    sma = sum(values[:min(period, len(values))]) / min(period, len(values))
    curr = sma
    for i, v in enumerate(values):
        if i < period:
            curr = (curr * i + v) / (i + 1)
        else:
            curr = v * k + curr * (1.0 - k)
        ema.append(curr)
    return ema

def calculate_rsi(closes: List[float], period: int = 8) -> List[float]:
    """Menghitung Relative Strength Index (RSI Periode 8)"""
    if len(closes) < 2:
        return [50.0] * len(closes)
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))
    
    rsi = [50.0]
    avg_gain = sum(gains[:period]) / max(1, period)
    avg_loss = sum(losses[:period]) / max(1, period)
    
    for i in range(len(gains)):
        if i < period:
            rsi.append(50.0)
            continue
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100.0 - (100.0 / (1.0 + rs)))
    return rsi

def calculate_sma(values: List[float], period: int = 9) -> List[float]:
    """Menghitung Simple Moving Average (SMA Periode 9)"""
    n = len(values)
    sma = []
    for i in range(n):
        start_idx = max(0, i - period + 1)
        window = values[start_idx : i + 1]
        sma.append(sum(window) / len(window))
    return sma

def calculate_bollinger_bands(closes: List[float], period: int = 20, dev: float = 2.0):
    """Menghitung Bollinger Bands (Periode 20, Selisih/Deviasi 2.0)"""
    n = len(closes)
    bb_mid = []
    bb_upper = []
    bb_lower = []
    for i in range(n):
        start_idx = max(0, i - period + 1)
        win = closes[start_idx : i + 1]
        m = sum(win) / len(win)
        variance = sum((x - m) ** 2 for x in win) / len(win)
        std = math.sqrt(variance)
        bb_mid.append(m)
        bb_upper.append(m + dev * std)
        bb_lower.append(m - dev * std)
    return bb_mid, bb_upper, bb_lower

def calculate_psar(highs: List[float], lows: List[float], step: float = 0.02, max_step: float = 0.20):
    """Menghitung Parabolic SAR (Langkah 0.02, Maksimum 0.20)"""
    n = len(highs)
    sar = [0.0] * n
    trend = [1] * n
    if n < 2:
        return sar, trend

    is_up = highs[1] >= highs[0]
    trend[0] = 1 if is_up else -1
    trend[1] = trend[0]
    ep = highs[0] if is_up else lows[0]
    af = step
    sar[0] = lows[0] if is_up else highs[0]
    sar[1] = sar[0]

    for i in range(2, n):
        prev_sar = sar[i - 1]
        if trend[i - 1] == 1:
            cur_sar = prev_sar + af * (ep - prev_sar)
            cur_sar = min(cur_sar, lows[i - 1], lows[i - 2])
            if lows[i] < cur_sar:
                trend[i] = -1
                sar[i] = ep
                ep = lows[i]
                af = step
            else:
                trend[i] = 1
                sar[i] = cur_sar
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + step, max_step)
        else:
            cur_sar = prev_sar + af * (ep - prev_sar)
            cur_sar = max(cur_sar, highs[i - 1], highs[i - 2])
            if highs[i] > cur_sar:
                trend[i] = 1
                sar[i] = ep
                ep = highs[i]
                af = step
            else:
                trend[i] = -1
                sar[i] = cur_sar
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + step, max_step)
    return sar, trend

def calculate_macd(closes: List[float], fast: int = 12, slow: int = 26):
    """Menghitung MACD Line (EMA Cepat 12, EMA Lambat 26, Signal SMA 1)"""
    ema_fast = calculate_ema(closes, fast)
    ema_slow = calculate_ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    return macd_line

class YUZARE_Engine:
    def __init__(self, atr_period: int = 12, qrr_mult: float = 1.4, swing_lookback: int = 6):
        self.atr_period = atr_period
        self.qrr_mult = qrr_mult
        self.swing_lookback = swing_lookback

    def analyze(
        self, 
        candles: List[Dict[str, Any]], 
        sl_pips: float = 30.0, 
        tp1_pips: float = 30.0, 
        tp2_pips: float = 50.0, 
        tp3_pips: float = 70.0, 
        tp4_pips: float = 100.0,
        tp_list: Optional[List[float]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if tp_list is None or len(tp_list) == 0:
            tp_list = [tp1_pips, tp2_pips, tp3_pips, tp4_pips]

        n = len(candles)
        if n < 25:
            return {
                "candles": candles,
                "signals": [],
                "pending_zones": [],
                "active_buy_trades": [],
                "active_sell_trades": [],
                "trade_history": [],
                "stats": {"win_rate": 0, "total_signals": 0}
            }

        closes = [c["close"] for c in candles]
        opens = [c["open"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        times = [c["time"] for c in candles]

        # Calculate indicators
        atr = calculate_atr(candles, self.atr_period)
        ema_fast = calculate_ema(closes, 9)
        ema_slow = calculate_ema(closes, 21)

        # 5 MT5 Confluence Indicators (User's Exact MT5 mobile setup):
        # 1. Moving Average: SMA 9 (Metode: Mudah / Simple, Tutup)
        sma9 = calculate_sma(closes, 9)
        # 2. Bollinger Bands: Periode 20, Deviasi 2.0, Tutup
        bb_mid, bb_upper, bb_lower = calculate_bollinger_bands(closes, 20, 2.0)
        # 3. Parabolic SAR: Langkah 0.02, Maksimum 0.20
        sar, sar_trend = calculate_psar(highs, lows, 0.02, 0.20)
        # 4. RSI: Periode 8, Level 30 & 70, Tutup
        rsi8 = calculate_rsi(closes, 8)
        # 5. MACD: EMA Cepat 12, EMA Lambat 26, Signal SMA 1, Tutup
        macd = calculate_macd(closes, 12, 26)

        # QRR Volatility Bands
        hl2 = [(h + l) / 2.0 for h, l in zip(highs, lows)]
        up_band = [hl2[i] - self.qrr_mult * atr[i] for i in range(n)]
        dn_band = [hl2[i] + self.qrr_mult * atr[i] for i in range(n)]

        trend = [1] * n
        for i in range(1, n):
            if closes[i - 1] > up_band[i - 1]:
                up_band[i] = max(up_band[i], up_band[i - 1])
            if closes[i - 1] < dn_band[i - 1]:
                dn_band[i] = min(dn_band[i], dn_band[i - 1])

            if closes[i] > dn_band[i - 1]:
                trend[i] = 1
            elif closes[i] < up_band[i - 1]:
                trend[i] = -1
            else:
                trend[i] = trend[i - 1]

        # 1. Candlestick Coloring: Hijau (Bullish) & Merah (Bearish)
        colored_candles = []
        for i in range(n):
            c = candles[i]
            is_bull = c["close"] >= c["open"]
            is_uptrend = trend[i] == 1

            # Vivid Green (#00C853) vs Vivid Red (#F23645)
            if is_bull:
                color = "#00c853" if is_uptrend else "#089981"
            else:
                color = "#f23645" if not is_uptrend else "#d50000"

            colored_candles.append({
                "time": c["time"],
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c.get("volume", 0),
                "color": color
            })

        # 2. Identify Pending Zones (Forward-projected Support & Resistance / Order Blocks)
        pending_zones = []
        swing_highs = []
        swing_lows = []

        lookback = self.swing_lookback
        for i in range(lookback, n - lookback):
            # Swing High (Resistance)
            is_sh = all(highs[i] >= highs[i - k] and highs[i] >= highs[i + k] for k in range(1, lookback + 1))
            if is_sh:
                swing_highs.append({
                    "index": i,
                    "time": times[i],
                    "price": highs[i],
                    "zone_bound": min(opens[i], closes[i]),
                    "type": "pending_sell"
                })

            # Swing Low (Support)
            is_sl = all(lows[i] <= lows[i - k] and lows[i] <= lows[i + k] for k in range(1, lookback + 1))
            if is_sl:
                swing_lows.append({
                    "index": i,
                    "time": times[i],
                    "price": lows[i],
                    "zone_bound": max(opens[i], closes[i]),
                    "type": "pending_buy"
                })

        current_price = closes[-1]
        pip_unit = 0.1 if current_price > 1000 else 0.0001

        # Hanya ambil Pending Zones yang belum pernah tersentuh / tertembus oleh candle setelahnya
        untouched_sh = []
        for sh in swing_highs:
            if sh["price"] <= current_price:
                continue
            idx = sh["index"]
            penetrated = any(highs[k] >= sh["price"] for k in range(idx + 1, n))
            if not penetrated:
                untouched_sh.append(sh)

        untouched_sl = []
        for sl in swing_lows:
            if sl["price"] >= current_price:
                continue
            idx = sl["index"]
            penetrated = any(lows[k] <= sl["price"] for k in range(idx + 1, n))
            if not penetrated:
                untouched_sl.append(sl)

        recent_sh = sorted(untouched_sh, key=lambda x: x["price"])[:2]
        recent_sl = sorted(untouched_sl, key=lambda x: x["price"], reverse=True)[:2]

        # Fallback jika pasar breakout ekstrim sehingga swing belum terbentuk di atas/bawah harga
        round_step = 10.0 if current_price > 1000 else 0.0050
        if len(recent_sh) == 0:
            target1 = math.ceil(current_price / round_step) * round_step
            p1 = target1 if target1 > current_price else current_price + round_step
            recent_sh = [
                {"index": n - 1, "price": p1, "zone_bound": p1 - (round_step * 0.3)},
                {"index": n - 1, "price": p1 + round_step, "zone_bound": p1 + (round_step * 0.7)}
            ]
        elif len(recent_sh) == 1:
            p_extra = recent_sh[0]["price"] + round_step
            recent_sh.append({"index": n - 1, "price": p_extra, "zone_bound": p_extra - (round_step * 0.3)})

        if len(recent_sl) == 0:
            target1 = math.floor(current_price / round_step) * round_step
            p1 = target1 if target1 < current_price else current_price - round_step
            recent_sl = [
                {"index": n - 1, "price": p1, "zone_bound": p1 + (round_step * 0.3)},
                {"index": n - 1, "price": p1 - round_step, "zone_bound": p1 - (round_step * 0.7)}
            ]
        elif len(recent_sl) == 1:
            p_extra = recent_sl[0]["price"] - round_step
            recent_sl.append({"index": n - 1, "price": p_extra, "zone_bound": p_extra + (round_step * 0.3)})

        for sh in recent_sh:
            pending_zones.append({
                "id": f"ps_{sh['index']}",
                "type": "pending_sell",
                "label": "SELL LIMIT",
                "price": round(sh["price"], 2),
                "zone_low": round(sh["zone_bound"], 2),
                "zone_high": round(sh["price"], 2),
                "distance": round(sh["price"] - current_price, 2),
                "distance_pips": round((sh["price"] - current_price) / pip_unit, 1)
            })

        for sl in recent_sl:
            pending_zones.append({
                "id": f"pb_{sl['index']}",
                "type": "pending_buy",
                "label": "BUY LIMIT",
                "price": round(sl["price"], 2),
                "zone_low": round(sl["price"], 2),
                "zone_high": round(sl["zone_bound"], 2),
                "distance": round(current_price - sl["price"], 2),
                "distance_pips": round((current_price - sl["price"]) / pip_unit, 1)
            })

        # 3. Dual Signal Generation (Zero Repaint - Confluence 5 Indikator MT5)
        signals = []
        buy_trades = []
        sell_trades = []
        active_buy_trades = []
        active_sell_trades = []

        last_buy_bar = -999
        last_sell_bar = -999
        cooldown = 4 # allow dual flow while keeping chart crisp

        for i in range(20, n):
            c_curr = candles[i]
            cur_atr = atr[i] if atr[i] > 0 else 1.0

            # 1. Moving Average SMA 9 Filter (Metode Mudah / Tutup)
            sma9_bull = closes[i] >= sma9[i]
            sma9_bear = closes[i] <= sma9[i]

            # 2. Parabolic SAR Filter (Langkah 0.02, Maksimum 0.20)
            sar_bull = (sar_trend[i] == 1)
            sar_bear = (sar_trend[i] == -1)
            sar_flip_bull = (sar_trend[i] == 1 and sar_trend[i - 1] == -1)
            sar_flip_bear = (sar_trend[i] == -1 and sar_trend[i - 1] == 1)

            # 3. Bollinger Bands Filter (20, 2.0 Tutup)
            bb_bull = (closes[i] <= bb_upper[i] + 0.15 * cur_atr) and (closes[i] >= bb_lower[i])
            bb_bear = (closes[i] >= bb_lower[i] - 0.15 * cur_atr) and (closes[i] <= bb_upper[i])

            # 4. RSI 8 Filter (Level 30 & 70 Tutup)
            rsi_bull = (32 <= rsi8[i] <= 78) and (rsi8[i] >= rsi8[i - 1] - 3.0 or rsi8[i] >= 48)
            rsi_bear = (22 <= rsi8[i] <= 68) and (rsi8[i] <= rsi8[i - 1] + 3.0 or rsi8[i] <= 52)

            # 5. MACD Filter (12, 26, Signal SMA 1)
            macd_bull = (macd[i] >= macd[i - 1]) or (macd[i] > 0)
            macd_bear = (macd[i] <= macd[i - 1]) or (macd[i] < 0)

            # Core YUZARE Triggers
            is_trend_flip_up = (trend[i] == 1 and trend[i - 1] == -1)
            is_pullback_buy = (trend[i] == 1 and closes[i] > opens[i] and lows[i] <= up_band[i] + 0.35 * cur_atr and closes[i] > closes[i - 1])
            is_breakout_buy = (trend[i] == 1 and closes[i] > max(closes[i - 1], closes[i - 2]) and (closes[i] - opens[i]) > 0.25 * cur_atr)
            buy_trigger = is_trend_flip_up or is_pullback_buy or is_breakout_buy or sar_flip_bull

            # BUY Confluence: Candle hijau + SMA9/SAR konfirmasi + BB dalam rentang + RSI 8 momentum + MACD naik
            buy_cond = (closes[i] > opens[i]) and (sma9_bull or sar_bull) and bb_bull and rsi_bull and macd_bull and buy_trigger

            is_trend_flip_dn = (trend[i] == -1 and trend[i - 1] == 1)
            is_pullback_sell = (trend[i] == -1 and closes[i] < opens[i] and highs[i] >= dn_band[i] - 0.35 * cur_atr and closes[i] < closes[i - 1])
            is_breakout_sell = (trend[i] == -1 and closes[i] < min(closes[i - 1], closes[i - 2]) and (opens[i] - closes[i]) > 0.25 * cur_atr)
            sell_trigger = is_trend_flip_dn or is_pullback_sell or is_breakout_sell or sar_flip_bear

            # SELL Confluence: Candle merah + SMA9/SAR konfirmasi + BB dalam rentang + RSI 8 momentum + MACD turun
            sell_cond = (closes[i] < opens[i]) and (sma9_bear or sar_bear) and bb_bear and rsi_bear and macd_bear and sell_trigger

            # BUY Trigger
            if buy_cond and (i - last_buy_bar >= cooldown):
                last_buy_bar = i
                entry = c_curr["close"]
                sl = entry - (sl_pips * pip_unit)
                tps = []
                for idx, p_val in enumerate(tp_list, start=1):
                    tp_price = round(entry + (p_val * pip_unit), 2)
                    tps.append({
                        "level": idx,
                        "pips": p_val,
                        "price": tp_price,
                        "hit": False
                    })

                trade = {
                    "id": f"BUY_{c_curr['time']}",
                    "type": "BUY",
                    "time": c_curr["time"],
                    "bar_index": i,
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tps": tps,
                    "sl_pips": sl_pips,
                    "risk": round(sl_pips * pip_unit, 2),
                    "status": "ACTIVE",
                    "exit_time": None,
                    "exit_price": None,
                    "max_rr_reached": 0.0
                }
                for t in tps:
                    trade[f"tp{t['level']}"] = t["price"]
                    trade[f"tp{t['level']}_hit"] = False

                buy_trades.append(trade)
                signals.append({
                    "time": c_curr["time"],
                    "type": "BUY",
                    "position": "belowBar",
                    "color": "#00C853",
                    "shape": "arrowUp",
                    "text": "buy",
                    "price": c_curr["low"],
                    "details": trade
                })

            # SELL Trigger (DUAL SIGNAL: Independent from BUY)
            if sell_cond and (i - last_sell_bar >= cooldown):
                last_sell_bar = i
                entry = c_curr["close"]
                sl = entry + (sl_pips * pip_unit)
                tps = []
                for idx, p_val in enumerate(tp_list, start=1):
                    tp_price = round(entry - (p_val * pip_unit), 2)
                    tps.append({
                        "level": idx,
                        "pips": p_val,
                        "price": tp_price,
                        "hit": False
                    })

                trade = {
                    "id": f"SELL_{c_curr['time']}",
                    "type": "SELL",
                    "time": c_curr["time"],
                    "bar_index": i,
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tps": tps,
                    "sl_pips": sl_pips,
                    "risk": round(sl_pips * pip_unit, 2),
                    "status": "ACTIVE",
                    "exit_time": None,
                    "exit_price": None,
                    "max_rr_reached": 0.0
                }
                for t in tps:
                    trade[f"tp{t['level']}"] = t["price"]
                    trade[f"tp{t['level']}_hit"] = False

                sell_trades.append(trade)
                signals.append({
                    "time": c_curr["time"],
                    "type": "SELL",
                    "position": "aboveBar",
                    "color": "#D50000",
                    "shape": "arrowDown",
                    "text": "sell",
                    "price": c_curr["high"],
                    "details": trade
                })

        # 4. Multi-Level Trade Outcome Evaluation (Dynamic TPs & SL)
        for trade in buy_trades:
            start_idx = trade["bar_index"] + 1
            trade["sl_hit"] = False
            trade["is_closed"] = False
            tps = trade.get("tps", [])
            for item in tps:
                item["hit"] = False
                trade[f"tp{item['level']}_hit"] = False

            for k in range(start_idx, n):
                h = candles[k]["high"]
                l = candles[k]["low"]

                # Target Hit Detection
                for item in tps:
                    if h >= item["price"]:
                        item["hit"] = True
                        trade[f"tp{item['level']}_hit"] = True

                # If final TP hit -> close trade
                if tps and tps[-1]["hit"]:
                    trade["status"] = f"TP{len(tps)} HIT 🎯"
                    trade["is_closed"] = True
                    trade["exit_time"] = candles[k]["time"]
                    trade["exit_price"] = tps[-1]["price"]
                    break

                # SL Hit
                if l <= trade["sl"]:
                    trade["sl_hit"] = True
                    trade["status"] = "SL HIT"
                    trade["is_closed"] = True
                    trade["exit_time"] = candles[k]["time"]
                    trade["exit_price"] = trade["sl"]
                    break

            if not trade["is_closed"]:
                hit_lvls = [item["level"] for item in tps if item["hit"]]
                if hit_lvls:
                    trade["status"] = f"TP{max(hit_lvls)} HIT ✓"
                else:
                    trade["status"] = "ACTIVE"
                active_buy_trades.append(trade)

        for trade in sell_trades:
            start_idx = trade["bar_index"] + 1
            trade["sl_hit"] = False
            trade["is_closed"] = False
            tps = trade.get("tps", [])
            for item in tps:
                item["hit"] = False
                trade[f"tp{item['level']}_hit"] = False

            for k in range(start_idx, n):
                h = candles[k]["high"]
                l = candles[k]["low"]

                for item in tps:
                    if l <= item["price"]:
                        item["hit"] = True
                        trade[f"tp{item['level']}_hit"] = True

                if tps and tps[-1]["hit"]:
                    trade["status"] = f"TP{len(tps)} HIT 🎯"
                    trade["is_closed"] = True
                    trade["exit_time"] = candles[k]["time"]
                    trade["exit_price"] = tps[-1]["price"]
                    break

                if h >= trade["sl"]:
                    trade["sl_hit"] = True
                    trade["status"] = "SL HIT"
                    trade["is_closed"] = True
                    trade["exit_time"] = candles[k]["time"]
                    trade["exit_price"] = trade["sl"]
                    break

            if not trade["is_closed"]:
                hit_lvls = [item["level"] for item in tps if item["hit"]]
                if hit_lvls:
                    trade["status"] = f"TP{max(hit_lvls)} HIT ✓"
                else:
                    trade["status"] = "ACTIVE"
                active_sell_trades.append(trade)

        # Calculate Statistics dynamically for the selected timeframe
        all_completed = [t for t in (buy_trades + sell_trades) if t["is_closed"] or any(item.get("hit") for item in t.get("tps", [])) or t.get("sl_hit")]
        tp_hits = [t for t in all_completed if any(item.get("hit") for item in t.get("tps", [])) or "TP" in t.get("status", "")]
        sl_hits = [t for t in all_completed if (t.get("sl_hit") or t.get("status") == "SL HIT") and not any(item.get("hit") for item in t.get("tps", []))]
        total_signals = len(signals)
        total_decided = len(tp_hits) + len(sl_hits)
        win_rate = (len(tp_hits) / total_decided * 100.0) if total_decided > 0 else 0.0

        mt5_indicators = {
            "sma9": round(sma9[-1], 2) if sma9 else 0.0,
            "bb_upper": round(bb_upper[-1], 2) if bb_upper else 0.0,
            "bb_mid": round(bb_mid[-1], 2) if bb_mid else 0.0,
            "bb_lower": round(bb_lower[-1], 2) if bb_lower else 0.0,
            "sar": round(sar[-1], 2) if sar else 0.0,
            "sar_trend": "BULLISH" if sar_trend and sar_trend[-1] == 1 else "BEARISH",
            "rsi8": round(rsi8[-1], 2) if rsi8 else 50.0,
            "macd": round(macd[-1], 2) if macd else 0.0
        }

        stats = {
            "total_signals": total_signals,
            "completed_trades": total_decided,
            "tp_hits": len(tp_hits),
            "sl_hits": len(sl_hits),
            "win_rate": round(win_rate, 1),
            "active_buy_count": len(active_buy_trades),
            "active_sell_count": len(active_sell_trades),
            "indicators": mt5_indicators
        }

        latest_buy = active_buy_trades[-1] if active_buy_trades else (buy_trades[-1] if buy_trades else None)
        latest_sell = active_sell_trades[-1] if active_sell_trades else (sell_trades[-1] if sell_trades else None)

        return {
            "candles": colored_candles,
            "signals": signals,
            "pending_zones": pending_zones,
            "active_buy_trades": active_buy_trades,
            "active_sell_trades": active_sell_trades,
            "latest_buy": latest_buy,
            "latest_sell": latest_sell,
            "stats": stats,
            "current_price": current_price,
            "indicators": mt5_indicators
        }

# Backward compatibility alias
TRXC_QRR_Engine = YUZARE_Engine

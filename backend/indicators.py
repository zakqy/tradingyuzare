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

def calculate_rsi(closes: List[float], period: int = 14) -> List[float]:
    """Menghitung Relative Strength Index (RSI)"""
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
        **kwargs
    ) -> Dict[str, Any]:
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
        rsi = calculate_rsi(closes, 14)

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

        for sh in recent_sh:
            pending_zones.append({
                "id": f"ps_{sh['index']}",
                "type": "pending_sell",
                "label": "pending sell",
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
                "label": "pending buy",
                "price": round(sl["price"], 2),
                "zone_low": round(sl["price"], 2),
                "zone_high": round(sl["zone_bound"], 2),
                "distance": round(current_price - sl["price"], 2),
                "distance_pips": round((current_price - sl["price"]) / pip_unit, 1)
            })

        # 3. Dual Signal Generation (Zero Repaint - Bar Close Evaluated)
        signals = []
        buy_trades = []
        sell_trades = []
        active_buy_trades = []
        active_sell_trades = []

        last_buy_bar = -999
        last_sell_bar = -999
        cooldown = 4 # allow dual flow while keeping chart crisp

        for i in range(15, n):
            c_curr = candles[i]
            cur_atr = atr[i] if atr[i] > 0 else 1.0

            # Trend reversal trigger or trend pullback continuation
            # BUY:
            # 1. Trend flipped from -1 to 1 (Major reversal) OR
            # 2. In uptrend (trend==1), price dipped to EMA/lower wick and candle closed strong green
            is_trend_flip_up = (trend[i] == 1 and trend[i - 1] == -1)
            is_pullback_buy = (trend[i] == 1 and closes[i] > opens[i] and lows[i] <= up_band[i] + 0.3 * cur_atr and closes[i] > closes[i - 1])
            is_breakout_buy = (trend[i] == 1 and closes[i] > max(closes[i - 1], closes[i - 2]) and (closes[i] - opens[i]) > 0.3 * cur_atr)

            buy_cond = (is_trend_flip_up or is_pullback_buy or is_breakout_buy) and (closes[i] > opens[i]) and (rsi[i] >= 42)

            # SELL:
            # 1. Trend flipped from 1 to -1 (Major reversal) OR
            # 2. In downtrend (trend==-1), price rallied to EMA/upper wick and candle closed strong red
            is_trend_flip_dn = (trend[i] == -1 and trend[i - 1] == 1)
            is_pullback_sell = (trend[i] == -1 and closes[i] < opens[i] and highs[i] >= dn_band[i] - 0.3 * cur_atr and closes[i] < closes[i - 1])
            is_breakout_sell = (trend[i] == -1 and closes[i] < min(closes[i - 1], closes[i - 2]) and (opens[i] - closes[i]) > 0.3 * cur_atr)

            sell_cond = (is_trend_flip_dn or is_pullback_sell or is_breakout_sell) and (closes[i] < opens[i]) and (rsi[i] <= 58)

            # BUY Trigger
            if buy_cond and (i - last_buy_bar >= cooldown):
                last_buy_bar = i
                entry = c_curr["close"]
                sl = entry - (sl_pips * pip_unit)
                tp1 = entry + (tp1_pips * pip_unit)
                tp2 = entry + (tp2_pips * pip_unit)
                tp3 = entry + (tp3_pips * pip_unit)
                tp4 = entry + (tp4_pips * pip_unit)

                trade = {
                    "id": f"BUY_{c_curr['time']}",
                    "type": "BUY",
                    "time": c_curr["time"],
                    "bar_index": i,
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp1": round(tp1, 2),
                    "tp2": round(tp2, 2),
                    "tp3": round(tp3, 2),
                    "tp4": round(tp4, 2),
                    "sl_pips": sl_pips,
                    "risk": round(sl_pips * pip_unit, 2),
                    "status": "ACTIVE",
                    "exit_time": None,
                    "exit_price": None,
                    "max_rr_reached": 0.0
                }
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
                tp1 = entry - (tp1_pips * pip_unit)
                tp2 = entry - (tp2_pips * pip_unit)
                tp3 = entry - (tp3_pips * pip_unit)
                tp4 = entry - (tp4_pips * pip_unit)

                trade = {
                    "id": f"SELL_{c_curr['time']}",
                    "type": "SELL",
                    "time": c_curr["time"],
                    "bar_index": i,
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp1": round(tp1, 2),
                    "tp2": round(tp2, 2),
                    "tp3": round(tp3, 2),
                    "tp4": round(tp4, 2),
                    "sl_pips": sl_pips,
                    "risk": round(sl_pips * pip_unit, 2),
                    "status": "ACTIVE",
                    "exit_time": None,
                    "exit_price": None,
                    "max_rr_reached": 0.0
                }
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

        # 4. Multi-Level Trade Outcome Evaluation (TP1-4 & SL)
        for trade in buy_trades:
            start_idx = trade["bar_index"] + 1
            trade["tp1_hit"] = False
            trade["tp2_hit"] = False
            trade["tp3_hit"] = False
            trade["tp4_hit"] = False
            trade["sl_hit"] = False
            trade["is_closed"] = False

            for k in range(start_idx, n):
                h = candles[k]["high"]
                l = candles[k]["low"]

                # Target Hit Detection
                if h >= trade["tp1"]:
                    trade["tp1_hit"] = True

                if h >= trade["tp2"]:
                    trade["tp2_hit"] = True

                if h >= trade["tp3"]:
                    trade["tp3_hit"] = True

                if h >= trade["tp4"]:
                    trade["tp4_hit"] = True
                    trade["status"] = "TP4 HIT 🎯"
                    trade["is_closed"] = True
                    trade["exit_time"] = candles[k]["time"]
                    trade["exit_price"] = trade["tp4"]
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
                if trade["tp3_hit"]:
                    trade["status"] = "TP3 HIT ✓"
                elif trade["tp2_hit"]:
                    trade["status"] = "TP2 HIT ✓"
                elif trade["tp1_hit"]:
                    trade["status"] = "TP1 HIT ✓"
                else:
                    trade["status"] = "ACTIVE"
                active_buy_trades.append(trade)

        for trade in sell_trades:
            start_idx = trade["bar_index"] + 1
            trade["tp1_hit"] = False
            trade["tp2_hit"] = False
            trade["tp3_hit"] = False
            trade["tp4_hit"] = False
            trade["sl_hit"] = False
            trade["is_closed"] = False

            for k in range(start_idx, n):
                h = candles[k]["high"]
                l = candles[k]["low"]

                if l <= trade["tp1"]:
                    trade["tp1_hit"] = True

                if l <= trade["tp2"]:
                    trade["tp2_hit"] = True

                if l <= trade["tp3"]:
                    trade["tp3_hit"] = True

                if l <= trade["tp4"]:
                    trade["tp4_hit"] = True
                    trade["status"] = "TP4 HIT 🎯"
                    trade["is_closed"] = True
                    trade["exit_time"] = candles[k]["time"]
                    trade["exit_price"] = trade["tp4"]
                    break

                if h >= trade["sl"]:
                    trade["sl_hit"] = True
                    trade["status"] = "SL HIT"
                    trade["is_closed"] = True
                    trade["exit_time"] = candles[k]["time"]
                    trade["exit_price"] = trade["sl"]
                    break

            if not trade["is_closed"]:
                if trade["tp3_hit"]:
                    trade["status"] = "TP3 HIT ✓"
                elif trade["tp2_hit"]:
                    trade["status"] = "TP2 HIT ✓"
                elif trade["tp1_hit"]:
                    trade["status"] = "TP1 HIT ✓"
                else:
                    trade["status"] = "ACTIVE"
                active_sell_trades.append(trade)

        # Calculate Statistics
        all_completed = [t for t in (buy_trades + sell_trades) if t["status"] != "ACTIVE"]
        tp_hits = [t for t in all_completed if "TP" in t["status"]]
        sl_hits = [t for t in all_completed if t["status"] == "SL_HIT"]
        total_signals = len(signals)
        win_rate = (len(tp_hits) / len(all_completed) * 100.0) if all_completed else 0.0

        stats = {
            "total_signals": total_signals,
            "completed_trades": len(all_completed),
            "tp_hits": len(tp_hits),
            "sl_hits": len(sl_hits),
            "win_rate": round(win_rate, 1),
            "active_buy_count": len(active_buy_trades),
            "active_sell_count": len(active_sell_trades)
        }

        latest_buy = active_buy_trades[-1] if active_buy_trades else None
        latest_sell = active_sell_trades[-1] if active_sell_trades else None

        return {
            "candles": colored_candles,
            "signals": signals,
            "pending_zones": pending_zones,
            "active_buy_trades": active_buy_trades,
            "active_sell_trades": active_sell_trades,
            "latest_buy": latest_buy,
            "latest_sell": latest_sell,
            "stats": stats,
            "current_price": current_price
        }

# Backward compatibility alias
TRXC_QRR_Engine = YUZARE_Engine

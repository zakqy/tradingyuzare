/**
 * YUZARE Trading Terminal - Frontend Engine
 * Real-Time Charting, Zero-Repaint Indicator, Dual Signal, Pending Zones, and Audio Synthesizer
 * Supports both Local FastAPI Server AND Standalone GitHub Pages Serverless Mode!
 */

// State Management & Per-Timeframe Settings
const DEFAULT_TF_SETTINGS = {
  '1m': { sl_pips: 30, tp_targets: [30, 50] },
  '5m': { sl_pips: 30, tp_targets: [30, 50, 70] },
  '15m': { sl_pips: 35, tp_targets: [35, 60, 90, 120] },
  '30m': { sl_pips: 40, tp_targets: [40, 70, 100, 140] },
  '1h': { sl_pips: 50, tp_targets: [50, 90, 140, 200] },
  '4h': { sl_pips: 80, tp_targets: [80, 150, 220, 300] },
  '1d': { sl_pips: 120, tp_targets: [120, 200, 300, 450] },
  '1w': { sl_pips: 250, tp_targets: [250, 400, 600, 800] },
};

const ALL_TF_LIST = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w'];

function getStoredTFSettings() {
  const settings = JSON.parse(JSON.stringify(DEFAULT_TF_SETTINGS));
  try {
    const raw = localStorage.getItem('yuzare_tf_settings');
    if (raw) {
      const parsed = JSON.parse(raw);
      for (const k in parsed) {
        if (parsed[k] && Array.isArray(parsed[k].tp_targets) && parsed[k].tp_targets.length > 0) {
          settings[k] = parsed[k];
        }
      }
    } else {
      // Migrate legacy single tp_targets if available
      const legacyTP = localStorage.getItem('tp_targets');
      const legacySL = localStorage.getItem('sl_pips');
      if (legacyTP) {
        const parsedTP = JSON.parse(legacyTP);
        if (Array.isArray(parsedTP) && parsedTP.length > 0) {
          settings['1m'] = {
            sl_pips: parseFloat(legacySL) || 30,
            tp_targets: parsedTP.map(Number),
          };
        }
      }
    }
  } catch (e) {}
  return settings;
}

const initialTFSettings = getStoredTFSettings();
const initialTF = '1m';
const activeTFConf = initialTFSettings[initialTF] || { sl_pips: 30, tp_targets: [30, 50] };

const state = {
  symbol: 'XAUUSD',
  timeframe: initialTF,
  tf_settings: initialTFSettings,
  all_tf_stats: {},
  combined_stats: {
    win_rate: 0,
    total_signals: 0,
    tp_hits: 0,
    sl_hits: 0,
    completed_trades: 0,
  },
  offset: parseFloat(localStorage.getItem('offset_XAUUSD') || '8.5'),
  sl_pips: activeTFConf.sl_pips || 30,
  tp_targets: [...activeTFConf.tp_targets],
  tp1_pips: activeTFConf.tp_targets[0] || 30,
  tp2_pips: activeTFConf.tp_targets[1] || 50,
  tp3_pips: activeTFConf.tp_targets[2] || 70,
  tp4_pips: activeTFConf.tp_targets[3] || 100,
  pz_lookback: parseInt(localStorage.getItem('pz_lookback') || '7'),
  soundEnabled: true,
  chart: null,
  candleSeries: null,
  currentPriceLine: null,
  pendingPriceLines: [],
  tpslLines: [],
  candles: [],
  signals: [],
  pendingZones: [],
  activeBuy: null,
  activeSell: null,
  ws: null,
  countdownInterval: null,
  tickerPollInterval: null,
  lastTickTime: Date.now(),
  lastCandle: null,
  lastPrice: 0,
};

function applyTimeframeSettings(tf) {
  if (!state.tf_settings[tf]) {
    state.tf_settings[tf] = DEFAULT_TF_SETTINGS[tf] 
      ? JSON.parse(JSON.stringify(DEFAULT_TF_SETTINGS[tf]))
      : { sl_pips: 30, tp_targets: [30, 50] };
  }
  const conf = state.tf_settings[tf];
  state.sl_pips = conf.sl_pips || 30;
  state.tp_targets = (Array.isArray(conf.tp_targets) && conf.tp_targets.length > 0)
    ? [...conf.tp_targets]
    : [30, 50];
  state.tp1_pips = state.tp_targets[0] || 30;
  state.tp2_pips = state.tp_targets[1] || 50;
  state.tp3_pips = state.tp_targets[2] || 70;
  state.tp4_pips = state.tp_targets[3] || 100;
}

const PAIR_MAP = {
  XAUUSD: 'PAXGUSDT',
  BTCUSD: 'BTCUSDT',
  ETHUSD: 'ETHUSDT',
  SOLUSD: 'SOLUSDT',
  EURUSD: 'EURUSDT',
  GBPUSD: 'GBPUSDT',
};

// Web Audio API Synthesizer
class SoundSynthesizer {
  constructor() {
    this.ctx = null;
  }

  init() {
    if (!this.ctx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AudioContext();
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  playBuy() {
    if (!state.soundEnabled) return;
    this.init();
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    [523.25, 659.25, 783.99].forEach((freq, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, now + idx * 0.08);
      gain.gain.setValueAtTime(0.2, now + idx * 0.08);
      gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.25);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now + idx * 0.08);
      osc.stop(now + idx * 0.08 + 0.25);
    });
  }

  playSell() {
    if (!state.soundEnabled) return;
    this.init();
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    [783.99, 659.25, 523.25].forEach((freq, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(freq, now + idx * 0.08);
      gain.gain.setValueAtTime(0.15, now + idx * 0.08);
      gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.25);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now + idx * 0.08);
      osc.stop(now + idx * 0.08 + 0.25);
    });
  }

  playPendingAlert() {
    if (!state.soundEnabled) return;
    this.init();
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(440, now);
    osc.frequency.exponentialRampToValueAtTime(880, now + 0.15);
    gain.gain.setValueAtTime(0.15, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(now);
    osc.stop(now + 0.25);
  }
}

const sounds = new SoundSynthesizer();

// Initialize Lightweight Charts
function initChart() {
  const container = document.getElementById('chart-container');
  container.innerHTML = '';

  state.chart = LightweightCharts.createChart(container, {
    layout: {
      background: { color: '#0b0e14' },
      textColor: '#8b949e',
      fontSize: 11,
      fontFamily: "'JetBrains Mono', -apple-system, sans-serif",
    },
    grid: {
      vertLines: { color: 'rgba(35, 41, 54, 0.4)', style: 1 },
      horzLines: { color: 'rgba(35, 41, 54, 0.4)', style: 1 },
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {
        color: '#00c853',
        width: 1,
        style: 3,
        labelBackgroundColor: '#181d2a',
      },
      horzLine: {
        color: '#00c853',
        width: 1,
        style: 3,
        labelBackgroundColor: '#181d2a',
      },
    },
    rightPriceScale: {
      borderColor: '#232936',
      scaleMargins: { top: 0.15, bottom: 0.15 },
      autoScale: true,
      alignLabels: true,
    },
    timeScale: {
      borderColor: '#232936',
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 25,
      barSpacing: 9,
    },
    handleScroll: true,
    handleScale: true,
  });

  // Candlestick Series: Hijau (Bullish) & Merah (Bearish)
  state.candleSeries = state.chart.addCandlestickSeries({
    upColor: '#00c853',
    downColor: '#f23645',
    borderUpColor: '#00c853',
    borderDownColor: '#f23645',
    wickUpColor: '#00c853',
    wickDownColor: '#f23645',
    priceFormat: {
      type: 'price',
      precision: state.symbol === 'XAUUSD' ? 2 : 2,
      minMove: 0.01,
    },
  });

  // Automatic Responsive ResizeObserver: handles browser zoom in/out (100% <-> 90%) and viewport changes
  if (window.ResizeObserver) {
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0 && state.chart) {
          state.chart.applyOptions({
            width: Math.floor(width),
            height: Math.floor(height),
          });
          renderPendingZonesOverlay();
          renderSignalBadges();
        }
      }
    });
    resizeObserver.observe(container);
  }

  window.addEventListener('resize', () => {
    const isDesktop = window.innerWidth > 960;
    const sidebarEl = document.querySelector('.sidebar');
    const chartWrapperEl = document.querySelector('.chart-wrapper');
    if (isDesktop) {
      if (sidebarEl) sidebarEl.classList.remove('mobile-active');
      if (chartWrapperEl) {
        chartWrapperEl.classList.remove('mobile-hidden');
        chartWrapperEl.style.display = '';
      }
    }
    if (state.chart) {
      const c = document.getElementById('chart-container');
      if (c && c.clientWidth > 0 && c.clientHeight > 0) {
        state.chart.applyOptions({
          width: c.clientWidth,
          height: c.clientHeight,
        });
        renderPendingZonesOverlay();
        renderSignalBadges();
      }
    }
  });

  state.chart.timeScale().subscribeVisibleTimeRangeChange(() => {
    renderPendingZonesOverlay();
    renderSignalBadges();
  });

  state.chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
    renderSignalBadges();
  });
}

function getPipUnit(symbol, price) {
  if (symbol === 'XAUUSD') return 0.1; // 1 pip = $0.10 (30p = $3.00, 50p = $5.00, 70p = $7.00, 100p = $10.00)
  if (symbol === 'BTCUSD') return 1.0;
  if (symbol === 'ETHUSD') return 0.1;
  if (symbol === 'SOLUSD') return 0.01;
  if (symbol === 'EURUSD' || symbol === 'GBPUSD') return 0.0001;
  return price > 500 ? 0.1 : 0.0001;
}

// Client-Side Calculation Engine (For Standalone GitHub Pages Mode)
function computeClientSideIndicators(candles, tf = state.timeframe) {
  const n = candles.length;
  if (n < 20) return { candles, signals: [], pending_zones: [], stats: { win_rate: 0, total_signals: 0, tp_hits: 0, sl_hits: 0 } };

  const conf = (state.tf_settings && state.tf_settings[tf]) 
    ? state.tf_settings[tf] 
    : { sl_pips: state.sl_pips, tp_targets: state.tp_targets };
  const slPips = conf.sl_pips || state.sl_pips || 30;
  const tpList = (conf.tp_targets && conf.tp_targets.length > 0) ? conf.tp_targets : [30, 50];

  const closes = candles.map(c => c.close);
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);

  // ATR
  const trs = [highs[0] - lows[0]];
  for (let i = 1; i < n; i++) {
    trs.push(Math.max(highs[i] - lows[i], Math.abs(highs[i] - closes[i - 1]), Math.abs(lows[i] - closes[i - 1])));
  }
  const atr = [];
  let a = trs.slice(0, 14).reduce((acc, v) => acc + v, 0) / 14;
  for (let i = 0; i < 14; i++) atr.push(a);
  for (let i = 14; i < n; i++) {
    a = (a * 13 + trs[i]) / 14;
    atr.push(a);
  }

  // Trend & QRR Bands
  const up_band = [];
  const dn_band = [];
  const trend = [];
  for (let i = 0; i < n; i++) {
    const hl2 = (highs[i] + lows[i]) / 2;
    up_band.push(hl2 - 1.4 * atr[i]);
    dn_band.push(hl2 + 1.4 * atr[i]);
    trend.push(1);
  }

  for (let i = 1; i < n; i++) {
    if (closes[i - 1] > up_band[i - 1]) up_band[i] = Math.max(up_band[i], up_band[i - 1]);
    if (closes[i - 1] < dn_band[i - 1]) dn_band[i] = Math.min(dn_band[i], dn_band[i - 1]);
    if (closes[i] > dn_band[i - 1]) trend[i] = 1;
    else if (closes[i] < up_band[i - 1]) trend[i] = -1;
    else trend[i] = trend[i - 1];
  }

  // Colored Candles
  const colored = candles.map((c, i) => ({
    time: c.time,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
    volume: c.volume,
    color: c.close >= c.open ? (trend[i] === 1 ? '#00c853' : '#089981') : (trend[i] === -1 ? '#f23645' : '#d50000'),
  }));

  // Pending Zones (Hanya ambil level yang belum pernah tersentuh/tertembus)
  const pending_zones = [];
  const curPrice = closes[n - 1];
  const lookback = state.pz_lookback || 7;

  const raw_sh = [];
  const raw_sl = [];

  for (let i = lookback; i < n - lookback; i++) {
    let isSH = true, isSL = true;
    for (let k = 1; k <= lookback; k++) {
      if (highs[i] < highs[i - k] || highs[i] < highs[i + k]) isSH = false;
      if (lows[i] > lows[i - k] || lows[i] > lows[i + k]) isSL = false;
    }
    if (isSH && highs[i] > curPrice) {
      // Periksa apakah candle setelah i pernah menembus highs[i]
      let penetrated = false;
      for (let m = i + 1; m < n; m++) {
        if (highs[m] >= highs[i]) { penetrated = true; break; }
      }
      if (!penetrated) raw_sh.push({ index: i, price: highs[i] });
    }
    if (isSL && lows[i] < curPrice) {
      // Periksa apakah candle setelah i pernah menembus lows[i]
      let penetrated = false;
      for (let m = i + 1; m < n; m++) {
        if (lows[m] <= lows[i]) { penetrated = true; break; }
      }
      if (!penetrated) raw_sl.push({ index: i, price: lows[i] });
    }
  }

  // Ambil maksimal 2 level terdekat agar chart tetap bersih
  raw_sh.sort((a, b) => a.price - b.price);
  raw_sl.sort((a, b) => b.price - a.price);

  raw_sh.slice(0, 2).forEach(sh => {
    pending_zones.push({
      id: `ps_${sh.index}`,
      type: 'pending_sell',
      label: 'SELL LIMIT',
      price: Math.round(sh.price * 100) / 100,
      distance_pips: Math.round((sh.price - curPrice) * 10),
    });
  });

  raw_sl.slice(0, 2).forEach(sl => {
    pending_zones.push({
      id: `pb_${sl.index}`,
      type: 'pending_buy',
      label: 'BUY LIMIT',
      price: Math.round(sl.price * 100) / 100,
      distance_pips: Math.round((curPrice - sl.price) * 10),
    });
  });

  // Signals
  const signals = [];
  const buy_trades = [];
  const sell_trades = [];
  let lastBuy = -999, lastSell = -999;

  for (let i = 15; i < n; i++) {
    const isUp = trend[i] === 1 && (trend[i - 1] === -1 || closes[i] > closes[i - 1]);
    const isDn = trend[i] === -1 && (trend[i - 1] === 1 || closes[i] < closes[i - 1]);

    if (isUp && closes[i] > candles[i].open && i - lastBuy >= 5) {
      lastBuy = i;
      const entry = closes[i];
      const pipUnit = getPipUnit(state.symbol, entry);
      const slDist = slPips * pipUnit;

      const tps = tpList.map((pips, idx) => ({
        level: idx + 1,
        pips: pips,
        price: Math.round((entry + pips * pipUnit) * 100) / 100,
        hit: false,
      }));

      const trade = {
        id: `BUY_${candles[i].time}`,
        type: 'BUY',
        bar_index: i,
        entry: Math.round(entry * 100) / 100,
        sl: Math.round((entry - slDist) * 100) / 100,
        tps: tps,
        status: 'ACTIVE',
        sl_hit: false,
        is_closed: false,
      };
      tps.forEach(t => {
        trade[`tp${t.level}`] = t.price;
        trade[`tp${t.level}_hit`] = false;
      });

      // Evaluasi apakah trade sudah hit TP / SL oleh candle setelahnya
      for (let m = i + 1; m < n; m++) {
        for (let t of trade.tps) {
          if (highs[m] >= t.price) {
            t.hit = true;
            trade[`tp${t.level}_hit`] = true;
          }
        }
        if (trade.tps.length > 0 && trade.tps[trade.tps.length - 1].hit) {
          trade.status = `TP${trade.tps.length} HIT 🎯`;
          trade.is_closed = true;
          break;
        }
        if (lows[m] <= trade.sl) {
          trade.sl_hit = true;
          trade.status = 'SL HIT';
          trade.is_closed = true;
          break;
        }
      }
      if (!trade.is_closed) {
        const hitTps = trade.tps.filter(t => t.hit);
        if (hitTps.length > 0) {
          trade.status = `TP${hitTps[hitTps.length - 1].level} HIT ✓`;
        } else {
          trade.status = 'ACTIVE';
        }
      }

      buy_trades.push(trade);
      signals.push({ time: candles[i].time, type: 'BUY', position: 'belowBar', color: '#00C853', shape: 'arrowUp', text: 'buy', price: candles[i].low, details: trade });
    }

    if (isDn && closes[i] < candles[i].open && i - lastSell >= 5) {
      lastSell = i;
      const entry = closes[i];
      const pipUnit = getPipUnit(state.symbol, entry);
      const slDist = slPips * pipUnit;

      const tps = tpList.map((pips, idx) => ({
        level: idx + 1,
        pips: pips,
        price: Math.round((entry - pips * pipUnit) * 100) / 100,
        hit: false,
      }));

      const trade = {
        id: `SELL_${candles[i].time}`,
        type: 'SELL',
        bar_index: i,
        entry: Math.round(entry * 100) / 100,
        sl: Math.round((entry + slDist) * 100) / 100,
        tps: tps,
        status: 'ACTIVE',
        sl_hit: false,
        is_closed: false,
      };
      tps.forEach(t => {
        trade[`tp${t.level}`] = t.price;
        trade[`tp${t.level}_hit`] = false;
      });

      for (let m = i + 1; m < n; m++) {
        for (let t of trade.tps) {
          if (lows[m] <= t.price) {
            t.hit = true;
            trade[`tp${t.level}_hit`] = true;
          }
        }
        if (trade.tps.length > 0 && trade.tps[trade.tps.length - 1].hit) {
          trade.status = `TP${trade.tps.length} HIT 🎯`;
          trade.is_closed = true;
          break;
        }
        if (highs[m] >= trade.sl) {
          trade.sl_hit = true;
          trade.status = 'SL HIT';
          trade.is_closed = true;
          break;
        }
      }
      if (!trade.is_closed) {
        const hitTps = trade.tps.filter(t => t.hit);
        if (hitTps.length > 0) {
          trade.status = `TP${hitTps[hitTps.length - 1].level} HIT ✓`;
        } else {
          trade.status = 'ACTIVE';
        }
      }

      sell_trades.push(trade);
      signals.push({ time: candles[i].time, type: 'SELL', position: 'aboveBar', color: '#D50000', shape: 'arrowDown', text: 'sell', price: candles[i].high, details: trade });
    }
  }

  const activeBuys = buy_trades.filter(t => !t.is_closed);
  const activeSells = sell_trades.filter(t => !t.is_closed);

  // Real Dynamic Performance Stats Calculation for selected timeframe
  const allTrades = [...buy_trades, ...sell_trades];
  const allCompleted = allTrades.filter(t => t.is_closed || (t.tps && t.tps.some(x => x.hit)) || t.sl_hit);
  const tpHits = allCompleted.filter(t => (t.tps && t.tps.some(x => x.hit)) || (t.status && t.status.includes('TP')));
  const slHits = allCompleted.filter(t => (t.sl_hit || t.status === 'SL HIT') && !(t.tps && t.tps.some(x => x.hit)));
  const totalDecided = tpHits.length + slHits.length;
  const winRate = totalDecided > 0 ? Math.round((tpHits.length / totalDecided) * 1000) / 10 : 0;

  return {
    candles: colored,
    signals,
    pending_zones,
    latest_buy: activeBuys.length > 0 ? activeBuys[activeBuys.length - 1] : (buy_trades.length > 0 ? buy_trades[buy_trades.length - 1] : null),
    latest_sell: activeSells.length > 0 ? activeSells[activeSells.length - 1] : (sell_trades.length > 0 ? sell_trades[sell_trades.length - 1] : null),
    current_price: curPrice,
    stats: {
      total_signals: signals.length,
      completed_trades: totalDecided,
      win_rate: winRate,
      tp_hits: tpHits.length,
      sl_hits: slHits.length,
    },
  };
}

// Fetch Market Data (Supports Local API & Direct Binance API for GitHub Pages)
async function loadMarketData() {
  showToast('🔄 Memuat analisa YUZARE...', '⏳');
  try {
    let data = null;
    const isLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';

    if (isLocal) {
      try {
        const tpStr = (state.tp_targets || []).join(',');
        const url = `/api/analysis?symbol=${state.symbol}&timeframe=${state.timeframe}&sl_pips=${state.sl_pips}&tp_targets=${tpStr}&tp1_pips=${state.tp1_pips}&tp2_pips=${state.tp2_pips}&tp3_pips=${state.tp3_pips}&tp4_pips=${state.tp4_pips}`;
        const resp = await fetch(url);
        if (resp.ok) data = await resp.json();
      } catch (e) {
        console.warn('Local API failed, using direct Binance stream');
      }
    }

    // Direct Binance Vision API fallback for GitHub Pages!
    if (!data) {
      const binanceSym = PAIR_MAP[state.symbol] || 'PAXGUSDT';
      const klineUrl = `https://data-api.binance.vision/api/v3/klines?symbol=${binanceSym}&interval=${state.timeframe}&limit=250`;
      const resp = await fetch(klineUrl);
      const raw = await resp.json();
      const offset = state.symbol === 'XAUUSD' ? state.offset : 0.0;
      const rawCandles = raw.map(x => ({
        time: Math.floor(x[0] / 1000),
        open: Math.round((parseFloat(x[1]) + offset) * 100) / 100,
        high: Math.round((parseFloat(x[2]) + offset) * 100) / 100,
        low: Math.round((parseFloat(x[3]) + offset) * 100) / 100,
        close: Math.round((parseFloat(x[4]) + offset) * 100) / 100,
        volume: parseFloat(x[5]),
      }));
      data = computeClientSideIndicators(rawCandles);
    }

    state.candles = data.candles;
    state.signals = data.signals;
    state.pendingZones = data.pending_zones;
    state.activeBuy = data.latest_buy;
    state.activeSell = data.latest_sell;

    state.candleSeries.setData(state.candles);
    if (state.candles.length > 0) {
      state.lastCandle = { ...state.candles[state.candles.length - 1] };
    }

    applyMarkers(state.signals);
    renderPendingZonesOverlay();
    renderTPSLLines();
    updateSidebar(data);
    updateOHLC(state.candles[state.candles.length - 1]);

    // Auto-fetch multi-timeframe stats in background if not fully loaded yet
    const hasAllTFStats = ALL_TF_LIST.every(tf => state.all_tf_stats[tf] && state.all_tf_stats[tf].total_signals > 0);
    if (!hasAllTFStats) {
      loadAllTimeframeStats();
    }

    startWebSocket();
    startTickerHeartbeat();
    startCountdown();

    showToast(`✓ YUZARE Aktif · ${state.symbol} (${state.timeframe})`, '⚡');
  } catch (err) {
    console.error('Error loading data:', err);
    showToast('Gagal memuat feed chart', '❌');
  }
}

// Multi-Timeframe Background Loader (Aggregates 1M - 1W Stats)
let isFetchingAllStats = false;
async function loadAllTimeframeStats(force = false) {
  if (isFetchingAllStats && !force) return;
  isFetchingAllStats = true;

  try {
    const isLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
    if (isLocal) {
      try {
        const tpStr = (state.tp_targets || []).join(',');
        const resp = await fetch(`/api/stats/all?symbol=${state.symbol}&sl_pips=${state.sl_pips}&tp_targets=${tpStr}`);
        if (resp.ok) {
          const res = await resp.json();
          if (res.by_timeframe) {
            for (const tf in res.by_timeframe) {
              state.all_tf_stats[tf] = res.by_timeframe[tf];
            }
          }
          if (res.combined) {
            state.combined_stats = res.combined;
          }
          renderStatsDisplay();
          isFetchingAllStats = false;
          return;
        }
      } catch (e) {
        console.warn('Local /api/stats/all fallback to Binance client fetch');
      }
    }

    // Direct Binance Vision API for each timeframe (parallel fetch for maximum speed)
    const binanceSym = PAIR_MAP[state.symbol] || 'PAXGUSDT';
    const offset = state.symbol === 'XAUUSD' ? state.offset : 0.0;

    await Promise.all(
      ALL_TF_LIST.map(async (tf) => {
        if (!force && state.all_tf_stats[tf] && state.all_tf_stats[tf].total_signals > 0) {
          return;
        }
        try {
          const klineUrl = `https://data-api.binance.vision/api/v3/klines?symbol=${binanceSym}&interval=${tf}&limit=250`;
          const resp = await fetch(klineUrl);
          if (!resp.ok) return;
          const raw = await resp.json();
          const rawCandles = raw.map(x => ({
            time: Math.floor(x[0] / 1000),
            open: Math.round((parseFloat(x[1]) + offset) * 100) / 100,
            high: Math.round((parseFloat(x[2]) + offset) * 100) / 100,
            low: Math.round((parseFloat(x[3]) + offset) * 100) / 100,
            close: Math.round((parseFloat(x[4]) + offset) * 100) / 100,
            volume: parseFloat(x[5]),
          }));
          const analyzed = computeClientSideIndicators(rawCandles, tf);
          if (analyzed && analyzed.stats) {
            state.all_tf_stats[tf] = analyzed.stats;
          }
        } catch (err) {
          console.warn(`Multi-TF fetch error for ${tf}:`, err);
        }
      })
    );

    computeCombinedStats();
  } catch (err) {
    console.error('Error in loadAllTimeframeStats:', err);
  } finally {
    isFetchingAllStats = false;
  }
}

// Silent background refresh on bar close
async function refreshSignalsSilently() {
  try {
    const isLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
    if (isLocal) {
      const tpStr = (state.tp_targets || []).join(',');
      const url = `/api/analysis?symbol=${state.symbol}&timeframe=${state.timeframe}&sl_pips=${state.sl_pips}&tp_targets=${tpStr}&tp1_pips=${state.tp1_pips}&tp2_pips=${state.tp2_pips}&tp3_pips=${state.tp3_pips}&tp4_pips=${state.tp4_pips}`;
      const resp = await fetch(url);
      if (resp.ok) {
        const data = await resp.json();
        state.signals = data.signals;
        state.pendingZones = data.pending_zones;
        state.activeBuy = data.latest_buy;
        state.activeSell = data.latest_sell;
        applyMarkers(state.signals);
        renderPendingZonesOverlay();
        renderTPSLLines();
        updateSidebar(data);
        return;
      }
    }
    // Client-side refresh
    const data = computeClientSideIndicators(state.candles);
    applyMarkers(data.signals);
    state.pendingZones = data.pending_zones;
    state.activeBuy = data.latest_buy;
    state.activeSell = data.latest_sell;
    renderPendingZonesOverlay();
    renderTPSLLines();
    updateSidebar(data);
  } catch (e) {
    console.warn('Silent refresh error:', e);
  }
}

// Render TradingView Style Signal Badges (buy / sell)
function renderSignalBadges() {
  const overlay = document.getElementById('signals-overlay');
  if (!overlay || !state.chart || !state.candleSeries || !state.signals) return;
  overlay.innerHTML = '';

  const chartContainer = document.getElementById('chart-container');
  if (!chartContainer) return;
  const chartWidth = chartContainer.clientWidth;
  const chartHeight = chartContainer.clientHeight;

  state.signals.forEach(sig => {
    const x = state.chart.timeScale().timeToCoordinate(sig.time);
    if (x === null || x < 0 || x > chartWidth) return;

    const y = state.candleSeries.priceToCoordinate(sig.price);
    if (y === null || y < 0 || y > chartHeight) return;

    const isBuy = sig.type === 'BUY';
    const pill = document.createElement('div');
    pill.className = `signal-pill ${isBuy ? 'buy' : 'sell'}`;
    pill.textContent = isBuy ? 'buy' : 'sell';
    pill.style.left = `${x}px`;
    pill.style.top = `${y}px`;

    overlay.appendChild(pill);
  });
}

// Markers (Clear canvas arrow markers to eliminate clutter, use clean TV badges)
function applyMarkers(signals) {
  if (state.candleSeries) {
    state.candleSeries.setMarkers([]);
  }
  renderSignalBadges();
}

// Pending Zones Overlay & Price Lines (Garis BUY LIMIT & SELL LIMIT pada Chart & Axis Harga)
function renderPendingZonesOverlay() {
  const overlay = document.getElementById('pending-zones-overlay');
  if (!state.candleSeries) return;
  if (overlay) overlay.innerHTML = '';

  // 1. Bersihkan semua garis pending lama
  if (state.pendingPriceLines) {
    state.pendingPriceLines.forEach(line => {
      try { state.candleSeries.removePriceLine(line); } catch (e) {}
    });
  }
  state.pendingPriceLines = [];

  if (!state.pendingZones || state.pendingZones.length === 0) {
    const pzList = document.getElementById('pending-zones-list');
    if (pzList) pzList.innerHTML = '<div style="color: var(--text-muted); font-size: 11px; text-align: center; padding: 10px;">Semua level pending telah tersentuh / selesai.</div>';
    const countLabel = document.getElementById('pending-count-label');
    if (countLabel) countLabel.textContent = '0 Level Aktif';
    return;
  }

  const curPrice = state.lastPrice || (state.candles.length > 0 ? state.candles[state.candles.length - 1].close : 0);

  // 2. Filter: Hilangkan jika harga saat ini sudah mencapai/menyentuh pending level (Hit SELL LIMIT / BUY LIMIT)
  const activeSellLimits = state.pendingZones
    .filter(z => z.type === 'pending_sell' && curPrice < z.price)
    .sort((a, b) => a.price - b.price)
    .slice(0, 2);

  const activeBuyLimits = state.pendingZones
    .filter(z => z.type === 'pending_buy' && curPrice > z.price)
    .sort((a, b) => b.price - a.price)
    .slice(0, 2);

  const activeZones = [...activeSellLimits, ...activeBuyLimits];

  // 3. Render garis horizontal dashed dan badge label pada axis harga kanan chart
  activeZones.forEach(zone => {
    const isSell = zone.type === 'pending_sell';
    const color = isSell ? '#ff5252' : '#00c853';
    const title = isSell ? 'SELL LIMIT' : 'BUY LIMIT';

    try {
      const pLine = state.candleSeries.createPriceLine({
        price: zone.price,
        color: color,
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: title,
      });
      state.pendingPriceLines.push(pLine);
    } catch (e) {
      console.warn('Error creating pending price line:', e);
    }

    // 4. Floating tag di chart canvas overlay
    if (overlay) {
      const yCoord = state.candleSeries.priceToCoordinate(zone.price);
      if (yCoord !== null && yCoord >= 15 && yCoord <= overlay.clientHeight - 15) {
        const tag = document.createElement('div');
        tag.className = `zone-tag ${zone.type.replace('_', '-')}`;
        tag.style.top = `${yCoord}px`;
        tag.innerHTML = `<span>${title}</span> <span style="opacity: 0.85; font-size: 10px; font-weight: 600;">${zone.price.toFixed(2)}</span>`;
        overlay.appendChild(tag);
      }
    }
  });

  // 5. Update list pending zones di sidebar
  const countLabel = document.getElementById('pending-count-label');
  if (countLabel) countLabel.textContent = `${activeZones.length} Level Aktif`;

  const pzList = document.getElementById('pending-zones-list');
  if (pzList) {
    if (activeZones.length === 0) {
      pzList.innerHTML = '<div style="color: var(--text-muted); font-size: 11px; text-align: center; padding: 10px;">Semua level pending telah tersentuh / selesai.</div>';
    } else {
      pzList.innerHTML = activeZones.map(z => {
        const isSell = z.type === 'pending_sell';
        const color = isSell ? 'var(--sell-red)' : 'var(--buy-green)';
        const bg = isSell ? 'rgba(213, 0, 0, 0.12)' : 'rgba(0, 200, 83, 0.12)';
        const badgeText = isSell ? 'SELL LIMIT' : 'BUY LIMIT';
        const dist = Math.round(Math.abs(z.price - curPrice) * 10);
        return `
          <div style="display: flex; justify-content: space-between; align-items: center; background: ${bg}; padding: 6px 8px; border-radius: 4px; border-left: 3px solid ${color}; margin-bottom: 4px;">
            <div>
              <span style="font-weight: 700; color: ${color}; font-size: 10px;">${badgeText}</span>
              <span style="font-family: var(--font-mono); font-weight: 700; margin-left: 6px;">${z.price.toFixed(2)}</span>
            </div>
            <span style="color: var(--text-secondary); font-family: var(--font-mono); font-size: 10px;">${dist > 0 ? '+' : ''}${dist} pips</span>
          </div>
        `;
      }).join('');
    }
  }
}

// TP & SL Target Lines (Otomatis menghapus garis yang sudah terkena TP / SL)
function renderTPSLLines() {
  if (state.tpslLines) {
    state.tpslLines.forEach(line => {
      try { state.candleSeries.removePriceLine(line); } catch (e) {}
    });
  }
  state.tpslLines = [];

  const addLine = (price, title, color, style = LightweightCharts.LineStyle.Dashed, width = 1) => {
    if (!price || !state.candleSeries) return;
    try {
      const l = state.candleSeries.createPriceLine({
        price,
        color,
        lineWidth: width,
        lineStyle: style,
        axisLabelVisible: true,
        title
      });
      state.tpslLines.push(l);
    } catch (e) {
      console.warn('Error adding price line:', e);
    }
  };

  // Posisi BUY (Hanya garis level yang belum hit yang ditampilkan)
  if (state.activeBuy) {
    const b = state.activeBuy;
    const tps = b.tps || [];
    const anyTpRemaining = tps.length > 0 ? tps.some(t => !t.hit) : (!b.tp1_hit || !b.tp2_hit || !b.tp3_hit || !b.tp4_hit);
    const hasRemainingLevels = anyTpRemaining || !b.sl_hit;

    if (hasRemainingLevels) {
      addLine(b.entry, 'BUY Entry', '#90caf9', LightweightCharts.LineStyle.Dotted, 1);
    }
    
    if (!b.sl_hit) {
      addLine(b.sl, `BUY SL (${state.sl_pips}p)`, '#ff5252', LightweightCharts.LineStyle.Dashed, 1);
    }

    if (tps.length > 0) {
      tps.forEach((t, idx) => {
        if (!t.hit) {
          const isLast = idx === tps.length - 1;
          addLine(
            t.price,
            `BUY TP${t.level} (${t.pips}p)`,
            '#00c853',
            isLast ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dashed,
            isLast ? 2 : 1
          );
        }
      });
    } else {
      if (!b.tp1_hit && b.tp1) addLine(b.tp1, `BUY TP1 (${state.tp1_pips}p)`, '#00c853', LightweightCharts.LineStyle.Dashed, 1);
      if (!b.tp2_hit && b.tp2) addLine(b.tp2, `BUY TP2 (${state.tp2_pips}p)`, '#00c853', LightweightCharts.LineStyle.Dashed, 1);
      if (!b.tp3_hit && b.tp3) addLine(b.tp3, `BUY TP3 (${state.tp3_pips}p)`, '#00c853', LightweightCharts.LineStyle.Dashed, 1);
      if (!b.tp4_hit && b.tp4) addLine(b.tp4, `BUY TP4 (${state.tp4_pips}p)`, '#00c853', LightweightCharts.LineStyle.Solid, 2);
    }
  }

  // Posisi SELL (Hanya garis level yang belum hit yang ditampilkan)
  if (state.activeSell) {
    const s = state.activeSell;
    const tps = s.tps || [];
    const anyTpRemaining = tps.length > 0 ? tps.some(t => !t.hit) : (!s.tp1_hit || !s.tp2_hit || !s.tp3_hit || !s.tp4_hit);
    const hasRemainingLevels = anyTpRemaining || !s.sl_hit;

    if (hasRemainingLevels) {
      addLine(s.entry, 'SELL Entry', '#ce93d8', LightweightCharts.LineStyle.Dotted, 1);
    }
    
    if (!s.sl_hit) {
      addLine(s.sl, `SELL SL (${state.sl_pips}p)`, '#ff5252', LightweightCharts.LineStyle.Dashed, 1);
    }

    if (tps.length > 0) {
      tps.forEach((t, idx) => {
        if (!t.hit) {
          const isLast = idx === tps.length - 1;
          addLine(
            t.price,
            `SELL TP${t.level} (${t.pips}p)`,
            '#ff1744',
            isLast ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dashed,
            isLast ? 2 : 1
          );
        }
      });
    } else {
      if (!s.tp1_hit && s.tp1) addLine(s.tp1, `SELL TP1 (${state.tp1_pips}p)`, '#ff1744', LightweightCharts.LineStyle.Dashed, 1);
      if (!s.tp2_hit && s.tp2) addLine(s.tp2, `SELL TP2 (${state.tp2_pips}p)`, '#ff1744', LightweightCharts.LineStyle.Dashed, 1);
      if (!s.tp3_hit && s.tp3) addLine(s.tp3, `SELL TP3 (${state.tp3_pips}p)`, '#ff1744', LightweightCharts.LineStyle.Dashed, 1);
      if (!s.tp4_hit && s.tp4) addLine(s.tp4, `SELL TP4 (${state.tp4_pips}p)`, '#ff1744', LightweightCharts.LineStyle.Solid, 2);
    }
  }
}

// Generate Dynamic Sidebar Target Grid HTML
function renderTargetGridHTML(type, trade) {
  const isBuy = type === 'BUY';
  const prefix = isBuy ? 'buy' : 'sell';
  let tps = [];
  if (trade && trade.tps && trade.tps.length > 0) {
    tps = trade.tps;
  } else {
    tps = (state.tp_targets || [30, 50, 70, 100]).map((p, idx) => {
      let pr = null;
      if (trade && trade.entry) {
        const pipUnit = getPipUnit(state.symbol, trade.entry);
        pr = isBuy ? trade.entry + p * pipUnit : trade.entry - p * pipUnit;
      }
      return {
        level: idx + 1,
        pips: p,
        price: pr,
        hit: trade ? !!trade[`tp${idx + 1}_hit`] : false,
      };
    });
  }

  let html = '';
  tps.forEach(t => {
    const valText = t.price != null ? t.price.toFixed(2) : '--';
    html += `
      <div class="target-item ${t.hit ? 'hit' : ''}" id="${prefix}-target-tp${t.level}">
        <span>TP${t.level} (${t.pips}p):</span>
        <span id="${prefix}-tp${t.level}-val">${valText}</span>
      </div>
    `;
  });

  const slValText = trade && trade.sl != null ? trade.sl.toFixed(2) : '--';
  const slHit = trade ? !!trade.sl_hit : false;
  html += `
    <div class="target-item ${slHit ? 'hit' : ''}" id="${prefix}-target-sl" style="border-color: rgba(255, 61, 0, 0.4); grid-column: 1 / -1;">
      <span style="color: var(--sl-red);">SL (${state.sl_pips} pips):</span>
      <span id="${prefix}-sl-val" style="color: var(--sl-red);">${slValText}</span>
    </div>
  `;
  return html;
}

// Update Sidebar Data
function updateSidebar(data) {
  const curPrice = data.current_price;
  state.lastPrice = curPrice;

  if (state.activeBuy) {
    const b = state.activeBuy;
    if (b.tp1_hit || (b.tps && b.tps.some(x => x.hit))) b._counted_tp = true;
    if (b.sl_hit) b._counted_sl = true;
    const entryEl = document.getElementById('buy-entry-val');
    if (entryEl) entryEl.textContent = b.entry.toFixed(2);
    const bBadge = document.getElementById('buy-status-badge');
    if (bBadge) bBadge.textContent = b.status || 'ACTIVE';
  }

  if (state.activeSell) {
    const s = state.activeSell;
    if (s.tp1_hit || (s.tps && s.tps.some(x => x.hit))) s._counted_tp = true;
    if (s.sl_hit) s._counted_sl = true;
    const entryEl = document.getElementById('sell-entry-val');
    if (entryEl) entryEl.textContent = s.entry.toFixed(2);
    const sBadge = document.getElementById('sell-status-badge');
    if (sBadge) sBadge.textContent = s.status || 'ACTIVE';
  }

  const buyGrid = document.getElementById('buy-target-grid');
  if (buyGrid) {
    buyGrid.innerHTML = renderTargetGridHTML('BUY', state.activeBuy);
  }
  const sellGrid = document.getElementById('sell-target-grid');
  if (sellGrid) {
    sellGrid.innerHTML = renderTargetGridHTML('SELL', state.activeSell);
  }

  if (data.stats) {
    state.stats = { ...data.stats };
    state.all_tf_stats[state.timeframe] = { ...data.stats };
    computeCombinedStats();
  }
}

function computeCombinedStats() {
  let totalSignals = 0;
  let tpHits = 0;
  let slHits = 0;
  let completed = 0;

  for (const tf of ALL_TF_LIST) {
    const st = state.all_tf_stats[tf];
    if (st) {
      totalSignals += (st.total_signals || 0);
      tpHits += (st.tp_hits || 0);
      slHits += (st.sl_hits || 0);
      completed += (st.completed_trades || ((st.tp_hits || 0) + (st.sl_hits || 0)));
    }
  }

  const decided = tpHits + slHits;
  const winRate = decided > 0 ? Math.round((tpHits / decided) * 1000) / 10 : 0;

  state.combined_stats = {
    total_signals: totalSignals,
    tp_hits: tpHits,
    sl_hits: slHits,
    completed_trades: decided,
    win_rate: winRate,
  };

  renderStatsDisplay();
}

function renderStatsDisplay() {
  const statsToRender = (state.combined_stats && state.combined_stats.total_signals > 0)
    ? state.combined_stats
    : (state.stats || { win_rate: 0, total_signals: 0, tp_hits: 0, sl_hits: 0 });

  const wrEl = document.getElementById('stat-winrate');
  const sigEl = document.getElementById('stat-signals');
  const tpHitEl = document.getElementById('stat-tphits');
  const slHitEl = document.getElementById('stat-slhits');

  if (wrEl) wrEl.textContent = `${statsToRender.win_rate}%`;
  if (sigEl) sigEl.textContent = statsToRender.total_signals;
  if (tpHitEl) tpHitEl.textContent = statsToRender.tp_hits;
  if (slHitEl) slHitEl.textContent = statsToRender.sl_hits;
}

// Live Tick Update
function updateActiveCandle(time, open, high, low, close) {
  state.lastTickTime = Date.now();
  state.lastPrice = close;
  const candleUpdate = {
    time: time,
    open: open,
    high: high,
    low: low,
    close: close,
    color: close >= open ? '#00c853' : '#f23645',
  };
  state.lastCandle = candleUpdate;
  state.candleSeries.update(candleUpdate);
  updateOHLC(candleUpdate);
  updateSidebarPrice(close);
}

function applyPriceTick(price) {
  if (!price || price <= 0) return;
  state.lastTickTime = Date.now();
  state.lastPrice = price;

  if (state.lastCandle) {
    state.lastCandle.close = price;
    if (price > state.lastCandle.high) state.lastCandle.high = price;
    if (price < state.lastCandle.low) state.lastCandle.low = price;
    state.lastCandle.color = state.lastCandle.close >= state.lastCandle.open ? '#00c853' : '#f23645';
    state.candleSeries.update(state.lastCandle);
    updateOHLC(state.lastCandle);
  }
  updateSidebarPrice(price);
}

function updateSidebarPrice(currentPrice) {
  // Real-time Target Hit Check: langsung hapus garis jika sudah hit TP / SL / Pending Limit
  let needsTPSLRedraw = false;

  if (state.activeBuy) {
    const b = state.activeBuy;
    const tps = b.tps || [];
    tps.forEach((t, idx) => {
      if (currentPrice >= t.price && !t.hit) {
        t.hit = true;
        b[`tp${t.level}_hit`] = true;
        needsTPSLRedraw = true;

        if (t.level === 1 && !b._counted_tp) {
          b._counted_tp = true;
          if (state.stats) {
            state.stats.tp_hits = (state.stats.tp_hits || 0) + 1;
            const total = (state.stats.tp_hits || 0) + (state.stats.sl_hits || 0);
            state.stats.win_rate = total > 0 ? Math.round((state.stats.tp_hits / total) * 1000) / 10 : 0;
          }
          if (state.all_tf_stats[state.timeframe]) {
            state.all_tf_stats[state.timeframe].tp_hits = (state.all_tf_stats[state.timeframe].tp_hits || 0) + 1;
            const curTFHits = state.all_tf_stats[state.timeframe].tp_hits;
            const curTFSl = state.all_tf_stats[state.timeframe].sl_hits || 0;
            state.all_tf_stats[state.timeframe].win_rate = (curTFHits + curTFSl > 0) ? Math.round((curTFHits / (curTFHits + curTFSl)) * 1000) / 10 : 0;
          }
          computeCombinedStats();
        }

        if (idx === tps.length - 1) {
          b.is_closed = true;
          b.status = `TP${t.level} HIT 🎯`;
        }
      }
    });

    if (currentPrice <= b.sl && !b.sl_hit) {
      b.sl_hit = true;
      b.status = 'SL HIT';
      b.is_closed = true;
      needsTPSLRedraw = true;
      if (!b._counted_sl && !b._counted_tp) {
        b._counted_sl = true;
        if (state.stats) {
          state.stats.sl_hits = (state.stats.sl_hits || 0) + 1;
          const total = (state.stats.tp_hits || 0) + (state.stats.sl_hits || 0);
          state.stats.win_rate = total > 0 ? Math.round((state.stats.tp_hits / total) * 1000) / 10 : 0;
        }
        if (state.all_tf_stats[state.timeframe]) {
          state.all_tf_stats[state.timeframe].sl_hits = (state.all_tf_stats[state.timeframe].sl_hits || 0) + 1;
          const curTFHits = state.all_tf_stats[state.timeframe].tp_hits || 0;
          const curTFSl = state.all_tf_stats[state.timeframe].sl_hits;
          state.all_tf_stats[state.timeframe].win_rate = (curTFHits + curTFSl > 0) ? Math.round((curTFHits / (curTFHits + curTFSl)) * 1000) / 10 : 0;
        }
        computeCombinedStats();
      }
    }
  }

  if (state.activeSell) {
    const s = state.activeSell;
    const tps = s.tps || [];
    tps.forEach((t, idx) => {
      if (currentPrice <= t.price && !t.hit) {
        t.hit = true;
        s[`tp${t.level}_hit`] = true;
        needsTPSLRedraw = true;

        if (t.level === 1 && !s._counted_tp) {
          s._counted_tp = true;
          if (state.stats) {
            state.stats.tp_hits = (state.stats.tp_hits || 0) + 1;
            const total = (state.stats.tp_hits || 0) + (state.stats.sl_hits || 0);
            state.stats.win_rate = total > 0 ? Math.round((state.stats.tp_hits / total) * 1000) / 10 : 0;
          }
          if (state.all_tf_stats[state.timeframe]) {
            state.all_tf_stats[state.timeframe].tp_hits = (state.all_tf_stats[state.timeframe].tp_hits || 0) + 1;
            const curTFHits = state.all_tf_stats[state.timeframe].tp_hits;
            const curTFSl = state.all_tf_stats[state.timeframe].sl_hits || 0;
            state.all_tf_stats[state.timeframe].win_rate = (curTFHits + curTFSl > 0) ? Math.round((curTFHits / (curTFHits + curTFSl)) * 1000) / 10 : 0;
          }
          computeCombinedStats();
        }

        if (idx === tps.length - 1) {
          s.is_closed = true;
          s.status = `TP${t.level} HIT 🎯`;
        }
      }
    });

    if (currentPrice >= s.sl && !s.sl_hit) {
      s.sl_hit = true;
      s.status = 'SL HIT';
      s.is_closed = true;
      needsTPSLRedraw = true;
      if (!s._counted_sl && !s._counted_tp) {
        s._counted_sl = true;
        if (state.stats) {
          state.stats.sl_hits = (state.stats.sl_hits || 0) + 1;
          const total = (state.stats.tp_hits || 0) + (state.stats.sl_hits || 0);
          state.stats.win_rate = total > 0 ? Math.round((state.stats.tp_hits / total) * 1000) / 10 : 0;
        }
        if (state.all_tf_stats[state.timeframe]) {
          state.all_tf_stats[state.timeframe].sl_hits = (state.all_tf_stats[state.timeframe].sl_hits || 0) + 1;
          const curTFHits = state.all_tf_stats[state.timeframe].tp_hits || 0;
          const curTFSl = state.all_tf_stats[state.timeframe].sl_hits;
          state.all_tf_stats[state.timeframe].win_rate = (curTFHits + curTFSl > 0) ? Math.round((curTFHits / (curTFHits + curTFSl)) * 1000) / 10 : 0;
        }
        computeCombinedStats();
      }
    }
  }

  if (needsTPSLRedraw) {
    renderTPSLLines();
    if (state.activeBuy) {
      const bBadge = document.getElementById('buy-status-badge');
      if (bBadge) bBadge.textContent = state.activeBuy.status || 'ACTIVE';
      (state.activeBuy.tps || []).forEach(t => {
        const el = document.getElementById(`buy-target-tp${t.level}`);
        if (el) el.classList.toggle('hit', !!t.hit);
      });
      const slEl = document.getElementById('buy-target-sl');
      if (slEl) slEl.classList.toggle('hit', !!state.activeBuy.sl_hit);
    }
    if (state.activeSell) {
      const sBadge = document.getElementById('sell-status-badge');
      if (sBadge) sBadge.textContent = state.activeSell.status || 'ACTIVE';
      (state.activeSell.tps || []).forEach(t => {
        const el = document.getElementById(`sell-target-tp${t.level}`);
        if (el) el.classList.toggle('hit', !!t.hit);
      });
      const slEl = document.getElementById('sell-target-sl');
      if (slEl) slEl.classList.toggle('hit', !!state.activeSell.sl_hit);
    }
  }

  // Real-time Pending Limit Check: langsung hapus badge jika harga sudah menyentuh level
  if (state.pendingZones && state.pendingZones.length > 0) {
    const prevCount = state.pendingZones.length;
    state.pendingZones = state.pendingZones.filter(z => {
      if (z.type === 'pending_sell' && currentPrice >= z.price) return false;
      if (z.type === 'pending_buy' && currentPrice <= z.price) return false;
      return true;
    });
    if (state.pendingZones.length !== prevCount) {
      renderPendingZonesOverlay();
    }
  }

  // Update kartu sidebar
  if (state.activeBuy) {
    const pnl = currentPrice - state.activeBuy.entry;
    const pnlEl = document.getElementById('buy-pnl-val');
    if (pnlEl) {
      pnlEl.textContent = `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} pts`;
      pnlEl.style.color = pnl >= 0 ? 'var(--buy-green)' : 'var(--sell-red)';
    }
    const badge = document.getElementById('buy-status-badge');
    if (badge) badge.textContent = state.activeBuy.status || 'ACTIVE';
  }

  if (state.activeSell) {
    const pnl = state.activeSell.entry - currentPrice;
    const pnlEl = document.getElementById('sell-pnl-val');
    if (pnlEl) {
      pnlEl.textContent = `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} pts`;
      pnlEl.style.color = pnl >= 0 ? 'var(--buy-green)' : 'var(--sell-red)';
    }
    const badge = document.getElementById('sell-status-badge');
    if (badge) badge.textContent = state.activeSell.status || 'ACTIVE';
  }
}

// Update OHLC Header
function updateOHLC(c) {
  if (!c) return;
  const digits = 2;
  document.getElementById('val-open').textContent = c.open.toFixed(digits);
  document.getElementById('val-high').textContent = c.high.toFixed(digits);
  document.getElementById('val-low').textContent = c.low.toFixed(digits);
  document.getElementById('val-close').textContent = c.close.toFixed(digits);

  const diff = c.close - c.open;
  const pct = (diff / c.open) * 100;
  const chgEl = document.getElementById('val-chg');
  chgEl.textContent = `${diff >= 0 ? '+' : ''}${diff.toFixed(digits)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`;
  chgEl.style.color = diff >= 0 ? 'var(--buy-green)' : '#ff5252';

  const spread = 0.82;
  document.getElementById('quote-sell-price').textContent = (c.close - spread / 2).toFixed(digits);
  document.getElementById('quote-buy-price').textContent = (c.close + spread / 2).toFixed(digits);
  document.getElementById('spread-val').textContent = spread.toFixed(2);
}

// WebSocket Stream (Supports both Local WebSocket & Direct Binance Stream with 0ms MT5 Speed)
function startWebSocket() {
  if (state.ws) {
    try { state.ws.close(); } catch(e) {}
  }

  const isLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
  const binanceSym = (PAIR_MAP[state.symbol] || 'PAXGUSDT').toLowerCase();
  const offset = state.symbol === 'XAUUSD' ? state.offset : 0.0;

  let wsUrl = '';
  if (isLocal) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsUrl = `${protocol}//${window.location.host}/ws/live/${state.symbol}/${state.timeframe}`;
  } else {
    // Ultra-Fast Multi-Stream: aggTrade (0ms executions) + bookTicker (live Bid/Ask) + kline (bars)
    const streams = [
      `${binanceSym}@aggTrade`,
      `${binanceSym}@bookTicker`,
      `${binanceSym}@kline_${state.timeframe}`
    ].join('/');
    wsUrl = `wss://data-stream.binance.vision/stream?streams=${streams}`;
  }

  const statusText = document.getElementById('ws-status-text');
  statusText.textContent = `Connecting to real-time stream (${state.symbol})...`;

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    statusText.textContent = `Live Stream: Connected · 0ms MT5 Speed (${state.symbol} · ${state.timeframe})`;
  };

  state.ws.onmessage = (event) => {
    try {
      const raw = JSON.parse(event.data);

      if (raw.type === 'connected') return;

      // Handle direct Binance Stream or backend relayed stream
      if (raw.stream) {
        const stream = raw.stream;
        const d = raw.data;

        // 1. Instant Trade Execution Tick (0ms latency, exactly like MT5 ticks!)
        if (stream.includes('aggTrade')) {
          const tradePrice = Math.round((parseFloat(d.p) + offset) * 100) / 100;
          applyPriceTick(tradePrice);
        }
        // 2. Real-Time Bid/Ask Order Book Updates (Instant Spread & Market Watch!)
        else if (stream.includes('bookTicker')) {
          const bid = Math.round((parseFloat(d.b) + offset) * 100) / 100;
          const ask = Math.round((parseFloat(d.a) + offset) * 100) / 100;
          const spread = Math.round((ask - bid) * 100) / 100;
          const digits = (state.symbol === 'EURUSD' || state.symbol === 'GBPUSD') ? 4 : 2;

          const sellEl = document.getElementById('quote-sell-price');
          const buyEl = document.getElementById('quote-buy-price');
          const spreadEl = document.getElementById('spread-val');
          if (sellEl) sellEl.textContent = bid.toFixed(digits);
          if (buyEl) buyEl.textContent = ask.toFixed(digits);
          if (spreadEl) spreadEl.textContent = spread.toFixed(2);

          applyPriceTick(bid);
        }
        // 3. Kline Bar Updates (Bar close zero-repaint event)
        else if (stream.includes('kline')) {
          const k = d.k;
          updateActiveCandle(
            Math.floor(k.t / 1000),
            Math.round((parseFloat(k.o) + offset) * 100) / 100,
            Math.round((parseFloat(k.h) + offset) * 100) / 100,
            Math.round((parseFloat(k.l) + offset) * 100) / 100,
            Math.round((parseFloat(k.c) + offset) * 100) / 100
          );
          if (k.x) {
            sounds.playPendingAlert();
            refreshSignalsSilently();
          }
        }
      } else {
        if (raw.type === 'kline') {
          updateActiveCandle(raw.time, raw.open, raw.high, raw.low, raw.close);
          if (raw.is_closed) {
            sounds.playPendingAlert();
            refreshSignalsSilently();
          }
        } else if (raw.type === 'bookTicker') {
          const digits = (state.symbol === 'EURUSD' || state.symbol === 'GBPUSD') ? 4 : 2;
          const sellEl = document.getElementById('quote-sell-price');
          const buyEl = document.getElementById('quote-buy-price');
          const spreadEl = document.getElementById('spread-val');
          if (sellEl && raw.bid) sellEl.textContent = raw.bid.toFixed(digits);
          if (buyEl && raw.ask) buyEl.textContent = raw.ask.toFixed(digits);
          if (spreadEl && raw.spread !== undefined) spreadEl.textContent = raw.spread.toFixed(2);
          if (raw.price) applyPriceTick(raw.price);
        } else if (raw.type === 'ticker' || raw.type === 'trade') {
          applyPriceTick(raw.price);
        }
      }
    } catch (e) {
      console.error('WS parse error:', e);
    }
  };

  state.ws.onclose = () => {
    statusText.textContent = `Stream reconnecting...`;
    setTimeout(startWebSocket, 1000);
  };
}

// Fallback Heartbeat Ticker
function startTickerHeartbeat() {
  if (state.tickerPollInterval) clearInterval(state.tickerPollInterval);

  state.tickerPollInterval = setInterval(async () => {
    if (Date.now() - state.lastTickTime > 1500) {
      try {
        const isLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
        if (isLocal) {
          const resp = await fetch(`/api/ticker?symbol=${state.symbol}`);
          if (resp.ok) {
            const d = await resp.json();
            if (d.price && d.price > 0) applyPriceTick(d.price);
          }
        } else {
          const binanceSym = PAIR_MAP[state.symbol] || 'PAXGUSDT';
          const resp = await fetch(`https://data-api.binance.vision/api/v3/ticker/price?symbol=${binanceSym}`);
          if (resp.ok) {
            const d = await resp.json();
            const offset = state.symbol === 'XAUUSD' ? state.offset : 0.0;
            applyPriceTick(Math.round((parseFloat(d.price) + offset) * 100) / 100);
          }
        }
      } catch (e) {}
    }
  }, 1200);
}

// Countdown Timer for Bar Close
function startCountdown() {
  if (state.countdownInterval) clearInterval(state.countdownInterval);

  const getTfSeconds = (tf) => {
    if (tf.endsWith('m')) return parseInt(tf) * 60;
    if (tf.endsWith('h')) return parseInt(tf) * 3600;
    if (tf.endsWith('d')) return 86400;
    if (tf.endsWith('w')) return 604800;
    return 60;
  };

  const tfSecs = getTfSeconds(state.timeframe);

  state.countdownInterval = setInterval(() => {
    const now = Math.floor(Date.now() / 1000);
    const secsLeft = tfSecs - (now % tfSecs);
    const mins = Math.floor(secsLeft / 60);
    const secs = secsLeft % 60;
    const str = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    const timerEl = document.getElementById('countdown-timer');
    if (timerEl) timerEl.textContent = str;
  }, 1000);
}

// UI Event Handlers
function setupEventListeners() {
  const offsetDisplay = document.getElementById('offset-display');
  const updateOffsetDisplay = () => {
    if (offsetDisplay) {
      const sign = state.offset >= 0 ? '+' : '';
      offsetDisplay.textContent = `${sign}${state.offset.toFixed(2)}`;
    }
  };
  updateOffsetDisplay();

  const applyNewOffset = async (newOffset) => {
    state.offset = Math.round(newOffset * 100) / 100;
    updateOffsetDisplay();
    localStorage.setItem(`offset_${state.symbol}`, state.offset);
    try {
      await fetch(`/api/offset?symbol=${state.symbol}&offset=${state.offset}`, { method: 'POST' });
    } catch (e) {}
    loadMarketData();
    showToast(`Kalibrasi MT5: ${state.offset >= 0 ? '+' : ''}${state.offset.toFixed(2)} pts`, '⚖️');
  };

  const btnPlus = document.getElementById('btn-offset-plus');
  const btnMinus = document.getElementById('btn-offset-minus');
  if (btnPlus) btnPlus.addEventListener('click', () => applyNewOffset(state.offset + 0.5));
  if (btnMinus) btnMinus.addEventListener('click', () => applyNewOffset(state.offset - 0.5));

  // Pair Selector
  document.getElementById('pair-selector').addEventListener('change', (e) => {
    state.symbol = e.target.value;
    document.getElementById('wm-symbol-name').textContent = e.target.options[e.target.selectedIndex].text;
    const saved = localStorage.getItem(`offset_${state.symbol}`);
    state.offset = saved !== null ? parseFloat(saved) : (state.symbol === 'XAUUSD' ? 8.5 : 0.0);
    updateOffsetDisplay();
    loadMarketData();
  });

  // Timeframe Buttons
  const tfBtns = document.querySelectorAll('#tf-buttons .tf-btn');
  tfBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tfBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.timeframe = btn.dataset.tf;
      applyTimeframeSettings(state.timeframe);
      document.getElementById('wm-timeframe').textContent = state.timeframe;

      const isScalp = ['1m', '5m'].includes(state.timeframe);
      document.getElementById('trading-mode-label').textContent = isScalp 
        ? `${state.timeframe.toUpperCase()} SCALPING` 
        : `${state.timeframe.toUpperCase()} SWING`;

      loadMarketData();
    });
  });

  // Sound Toggle
  document.getElementById('btn-sound-toggle').addEventListener('click', () => {
    state.soundEnabled = !state.soundEnabled;
    document.getElementById('sound-icon').textContent = state.soundEnabled ? '🔊' : '🔇';
    document.getElementById('sound-label').textContent = state.soundEnabled ? 'Audio ON' : 'Audio MUTE';
    showToast(state.soundEnabled ? 'Suara alert diaktifkan' : 'Suara alert dimatikan', '🔊');
    if (state.soundEnabled) sounds.playBuy();
  });

  // Pine Script Modal
  const modalPine = document.getElementById('modal-pine');
  document.getElementById('btn-open-pine').addEventListener('click', async () => {
    modalPine.classList.add('active');
    const display = document.getElementById('pinescript-code-display');
    display.textContent = 'Memuat kode script...';
    try {
      const resp = await fetch('./YUZARE_Indicator.pine');
      if (resp.ok) {
        display.textContent = await resp.text();
      } else {
        display.textContent = '// Gagal memuat file pine script';
      }
    } catch (e) {
      display.textContent = '// Error: ' + e.message;
    }
  });

  document.getElementById('btn-close-pine').addEventListener('click', () => modalPine.classList.remove('active'));
  document.getElementById('btn-close-pine-bottom').addEventListener('click', () => modalPine.classList.remove('active'));

  document.getElementById('btn-copy-pine-clipboard').addEventListener('click', () => {
    const code = document.getElementById('pinescript-code-display').textContent;
    navigator.clipboard.writeText(code).then(() => {
      showToast('Pine Script v5 berhasil disalin!', '📋');
      modalPine.classList.remove('active');
    });
  });

  // Settings Modal with Per-Timeframe (+) and (-) TP Management
  const modalSettings = document.getElementById('modal-settings');
  let workingTFSettings = JSON.parse(JSON.stringify(state.tf_settings));
  let activeModalTF = state.timeframe;

  function syncModalInputsToWorking(tf) {
    if (!workingTFSettings[tf]) {
      workingTFSettings[tf] = { sl_pips: 30, tp_targets: [30, 50] };
    }
    const slInp = document.getElementById('inp-sl-pips');
    if (slInp) {
      workingTFSettings[tf].sl_pips = parseFloat(slInp.value) || workingTFSettings[tf].sl_pips || 30;
    }
    const tpInps = document.querySelectorAll('#tp-inputs-container .inp-tp-val');
    if (tpInps.length > 0) {
      const vals = [];
      tpInps.forEach(inp => {
        const v = parseFloat(inp.value);
        if (!isNaN(v) && v > 0) vals.push(v);
      });
      if (vals.length > 0) {
        workingTFSettings[tf].tp_targets = vals;
      }
    }
  }

  function renderModalForTimeframe(tf) {
    activeModalTF = tf;
    if (!workingTFSettings[tf]) {
      workingTFSettings[tf] = DEFAULT_TF_SETTINGS[tf] 
        ? JSON.parse(JSON.stringify(DEFAULT_TF_SETTINGS[tf]))
        : { sl_pips: 30, tp_targets: [30, 50] };
    }
    const conf = workingTFSettings[tf];

    // Highlight button in modal
    const modalTfButtons = document.querySelectorAll('#modal-tf-buttons .modal-tf-btn');
    modalTfButtons.forEach(b => {
      b.classList.toggle('active', b.dataset.tf === tf);
    });

    // Update label
    const tfLabel = document.getElementById('modal-active-tf-label');
    if (tfLabel) {
      const isScalp = ['1m', '5m'].includes(tf);
      tfLabel.textContent = `${tf.toUpperCase()} ${isScalp ? 'SCALPING' : 'SWING'}`;
    }

    // Set Stop Loss input
    const elSl = document.getElementById('inp-sl-pips');
    if (elSl) elSl.value = conf.sl_pips || 30;

    // Render TP inputs
    const container = document.getElementById('tp-inputs-container');
    const badge = document.getElementById('tp-count-badge');
    const tps = conf.tp_targets || [30, 50];
    if (badge) badge.textContent = `${tps.length} Level`;

    if (container) {
      container.innerHTML = tps.map((pips, idx) => `
        <div class="tp-input-row" data-index="${idx}" style="display: flex; justify-content: space-between; align-items: center;">
          <label style="color: var(--text-secondary); font-size: 13px;">TP${idx + 1} Target:</label>
          <div style="display: flex; align-items: center; gap: 4px;">
            <input type="number" class="inp-tp-val" data-index="${idx}" value="${pips}" min="5" max="2500" style="width: 70px; padding: 4px; background: var(--bg-card); border: 1px solid var(--border-color); color: #fff; border-radius: 4px; font-family: var(--font-mono);">
            <span style="color: var(--text-secondary); font-size: 11px;">pips</span>
          </div>
        </div>
      `).join('');

      container.querySelectorAll('.inp-tp-val').forEach(input => {
        input.addEventListener('input', (e) => {
          const idx = parseInt(e.target.dataset.index);
          const val = parseFloat(e.target.value) || 0;
          if (!isNaN(idx) && idx >= 0 && idx < workingTFSettings[activeModalTF].tp_targets.length) {
            workingTFSettings[activeModalTF].tp_targets[idx] = val;
          }
        });
      });
    }
  }

  // Timeframe selector buttons inside the modal
  const modalTfButtons = document.querySelectorAll('#modal-tf-buttons .modal-tf-btn');
  modalTfButtons.forEach(b => {
    b.addEventListener('click', () => {
      const targetTf = b.dataset.tf;
      if (targetTf === activeModalTF) return;
      // Sync current inputs before switching
      syncModalInputsToWorking(activeModalTF);
      // Switch to new timeframe tab in modal
      renderModalForTimeframe(targetTf);
    });
  });

  const btnAddTP = document.getElementById('btn-add-tp');
  if (btnAddTP) {
    btnAddTP.addEventListener('click', () => {
      syncModalInputsToWorking(activeModalTF);
      const list = workingTFSettings[activeModalTF].tp_targets;
      const lastVal = list.length > 0 ? list[list.length - 1] : 30;
      const step = list.length >= 2 ? (list[list.length - 1] - list[list.length - 2]) : 20;
      const newVal = Math.max(lastVal + (step > 0 ? step : 20), lastVal + 10);
      list.push(newVal);
      renderModalForTimeframe(activeModalTF);

      const container = document.getElementById('tp-inputs-container');
      if (container) container.scrollTop = container.scrollHeight;
      showToast(`[${activeModalTF.toUpperCase()}] Ditambahkan TP${list.length} (${newVal} pips)`, '➕');
    });
  }

  const btnRemoveTP = document.getElementById('btn-remove-tp');
  if (btnRemoveTP) {
    btnRemoveTP.addEventListener('click', () => {
      syncModalInputsToWorking(activeModalTF);
      const list = workingTFSettings[activeModalTF].tp_targets;
      if (list.length <= 1) {
        showToast('Minimal harus ada 1 level TP!', '⚠️');
        return;
      }
      const removedLevel = list.length;
      list.pop();
      renderModalForTimeframe(activeModalTF);
      showToast(`[${activeModalTF.toUpperCase()}] TP${removedLevel} berhasil dibuang`, '➖');
    });
  }

  document.getElementById('btn-open-settings').addEventListener('click', () => {
    modalSettings.classList.add('active');
    workingTFSettings = JSON.parse(JSON.stringify(state.tf_settings));
    renderModalForTimeframe(state.timeframe);
    const elPz = document.getElementById('inp-pz-lookback');
    if (elPz) elPz.value = state.pz_lookback;
  });

  document.getElementById('btn-close-settings').addEventListener('click', () => {
    modalSettings.classList.remove('active');
  });

  document.getElementById('btn-save-settings').addEventListener('click', () => {
    // Sync current active tab
    syncModalInputsToWorking(activeModalTF);

    state.pz_lookback = parseInt(document.getElementById('inp-pz-lookback').value) || 7;
    state.tf_settings = JSON.parse(JSON.stringify(workingTFSettings));

    // Save to localStorage
    localStorage.setItem('yuzare_tf_settings', JSON.stringify(state.tf_settings));
    localStorage.setItem('pz_lookback', state.pz_lookback);

    // Apply the settings for the currently active chart timeframe
    applyTimeframeSettings(state.timeframe);

    modalSettings.classList.remove('active');
    state.all_tf_stats = {};
    loadMarketData();
    loadAllTimeframeStats(true);
    showToast(`✓ Pengaturan disimpan! (${state.timeframe.toUpperCase()}: ${state.tp_targets.length} Level TP)`, '⚙️');
  });

  // Logout Buttons
  const btnLogout = document.getElementById('btn-logout');
  if (btnLogout) {
    btnLogout.addEventListener('click', () => {
      if (confirm('Apakah Anda yakin ingin keluar dari terminal?')) {
        logout();
      }
    });
  }
  const btnModalLogout = document.getElementById('btn-modal-logout');
  if (btnModalLogout) {
    btnModalLogout.addEventListener('click', () => {
      if (confirm('Apakah Anda yakin ingin keluar dari terminal?')) {
        logout();
      }
    });
  }

  // Mobile Bottom Navigation Tabs (Khusus Tampilan Handphone)
  const mobileNavBtns = document.querySelectorAll('.mobile-nav-btn');
  const sidebar = document.querySelector('.sidebar');
  const chartWrapper = document.querySelector('.chart-wrapper');

  mobileNavBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      mobileNavBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      if (tab === 'chart') {
        if (sidebar) sidebar.classList.remove('mobile-active');
        if (chartWrapper) {
          chartWrapper.classList.remove('mobile-hidden');
          chartWrapper.style.display = '';
        }
        setTimeout(() => {
          if (state.chart) {
            const container = document.getElementById('chart-container');
            if (container && container.clientWidth > 0 && container.clientHeight > 0) {
              state.chart.applyOptions({
                width: container.clientWidth,
                height: container.clientHeight,
              });
              renderPendingZonesOverlay();
              renderSignalBadges();
            }
          }
        }, 60);
      } else if (tab === 'signals') {
        if (chartWrapper) {
          chartWrapper.classList.add('mobile-hidden');
          chartWrapper.style.display = 'none';
        }
        if (sidebar) {
          sidebar.classList.add('mobile-active');
          sidebar.scrollTop = 0;
        }
      } else if (tab === 'pending') {
        if (chartWrapper) {
          chartWrapper.classList.add('mobile-hidden');
          chartWrapper.style.display = 'none';
        }
        if (sidebar) {
          sidebar.classList.add('mobile-active');
          const pzEl = document.getElementById('pending-zones-list');
          if (pzEl) pzEl.scrollIntoView({ behavior: 'smooth' });
        }
      } else if (tab === 'stats') {
        if (chartWrapper) {
          chartWrapper.classList.add('mobile-hidden');
          chartWrapper.style.display = 'none';
        }
        if (sidebar) {
          sidebar.classList.add('mobile-active');
          const statsEl = document.querySelector('.stats-grid');
          if (statsEl) statsEl.scrollIntoView({ behavior: 'smooth' });
        }
      } else if (tab === 'settings') {
        const modal = document.getElementById('modal-settings');
        if (modal) modal.classList.add('active');
        const chartBtn = document.getElementById('nav-btn-chart');
        if (chartBtn) {
          mobileNavBtns.forEach(b => b.classList.remove('active'));
          chartBtn.classList.add('active');
          if (sidebar) sidebar.classList.remove('mobile-active');
          if (chartWrapper) {
            chartWrapper.classList.remove('mobile-hidden');
            chartWrapper.style.display = '';
          }
        }
      }
    });
  });
}

function showToast(msg, icon = '🔔') {
  const toast = document.getElementById('toast-notification');
  document.getElementById('toast-icon').textContent = icon;
  document.getElementById('toast-message').textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

// ==========================================================
// AUTHENTICATION & ACCESS CONTROL SYSTEM
// ==========================================================
const AUTH_USERS = [
  { username: 'zakzakqy', password: 'Savior,123', name: 'zakzakqy' },
  { username: 'piterxzakqy', password: 'piterxzakqy123', name: 'piterxzakqy' }
];

let isTerminalInitialized = false;

function getLoggedUser() {
  try {
    const s = sessionStorage.getItem('yuzare_logged_user');
    if (s) return JSON.parse(s);
    const l = localStorage.getItem('yuzare_logged_user');
    if (l) return JSON.parse(l);
  } catch (e) {
    console.warn('Session parsing error:', e);
  }
  return null;
}

function setLoggedUser(userObj, remember) {
  try {
    sessionStorage.setItem('yuzare_logged_user', JSON.stringify(userObj));
    if (remember) {
      localStorage.setItem('yuzare_logged_user', JSON.stringify(userObj));
    } else {
      localStorage.removeItem('yuzare_logged_user');
    }
  } catch (e) {
    console.warn('Storage error:', e);
  }
}

function logout() {
  try {
    sessionStorage.removeItem('yuzare_logged_user');
    localStorage.removeItem('yuzare_logged_user');
  } catch (e) {}

  if (state.ws) {
    try { state.ws.close(); } catch (e) {}
    state.ws = null;
  }
  if (state.countdownInterval) clearInterval(state.countdownInterval);
  if (state.tickerPollInterval) clearInterval(state.tickerPollInterval);

  // Update UI Elements
  const badge = document.getElementById('user-profile-badge');
  const btnLogout = document.getElementById('btn-logout');
  if (badge) badge.style.display = 'none';
  if (btnLogout) btnLogout.style.display = 'none';

  const modalSettings = document.getElementById('modal-settings');
  if (modalSettings) modalSettings.classList.remove('active');

  const gate = document.getElementById('login-gate');
  if (gate) {
    gate.classList.remove('hidden');
    const pwdInput = document.getElementById('login-password');
    if (pwdInput) pwdInput.value = '';
    const errEl = document.getElementById('login-error');
    if (errEl) errEl.style.display = 'none';
  }

  showToast('Anda telah keluar dari terminal.', '👋');
}

function updateAuthUI(user) {
  const badge = document.getElementById('user-profile-badge');
  const btnLogout = document.getElementById('btn-logout');
  const nameEl = document.getElementById('user-display-name');
  const modalInfo = document.getElementById('modal-user-info');

  const displayName = user.name || user.username;
  if (nameEl) nameEl.textContent = displayName;
  if (modalInfo) modalInfo.textContent = 'Login sebagai: ' + displayName;
  if (badge) badge.style.display = 'flex';
  if (btnLogout) btnLogout.style.display = 'flex';
}

function startTerminal() {
  if (!isTerminalInitialized) {
    isTerminalInitialized = true;
    initChart();
    setupEventListeners();
    loadMarketData();
  } else {
    loadMarketData();
  }
}

function initAuth() {
  const gate = document.getElementById('login-gate');
  const form = document.getElementById('login-form');
  const usernameInput = document.getElementById('login-username');
  const passwordInput = document.getElementById('login-password');
  const rememberInput = document.getElementById('login-remember');
  const errorEl = document.getElementById('login-error');
  const errorText = document.getElementById('login-error-text');
  const togglePwdBtn = document.getElementById('btn-toggle-pwd');

  // Toggle Password Visibility
  if (togglePwdBtn && passwordInput) {
    togglePwdBtn.addEventListener('click', () => {
      const isPwd = passwordInput.getAttribute('type') === 'password';
      passwordInput.setAttribute('type', isPwd ? 'text' : 'password');
      togglePwdBtn.textContent = isPwd ? '🙈' : '👁️';
    });
  }

  // Check Existing Session
  const currentUser = getLoggedUser();
  if (currentUser && currentUser.username) {
    if (gate) gate.classList.add('hidden');
    updateAuthUI(currentUser);
    startTerminal();
  } else {
    if (gate) gate.classList.remove('hidden');
    setTimeout(() => {
      if (usernameInput) usernameInput.focus();
    }, 150);
  }

  // Handle Login Submit
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const rawUser = (usernameInput.value || '').trim();
      const rawPass = (passwordInput.value || '').trim();

      if (!rawUser || !rawPass) {
        if (errorEl && errorText) {
          errorText.textContent = 'Harap isi username dan password!';
          errorEl.style.display = 'flex';
        }
        return;
      }

      // Check against credentials (case-insensitive for username, exact match for password)
      const matched = AUTH_USERS.find(
        u => u.username.toLowerCase() === rawUser.toLowerCase() && u.password === rawPass
      );

      if (matched) {
        if (errorEl) errorEl.style.display = 'none';
        const userObj = {
          username: matched.username,
          name: matched.name,
          loginTime: Date.now()
        };
        const remember = rememberInput ? rememberInput.checked : true;
        setLoggedUser(userObj, remember);

        if (gate) gate.classList.add('hidden');
        updateAuthUI(userObj);
        startTerminal();
        showToast(`Selamat datang, ${matched.name}! 🚀`, '✅');
      } else {
        // Fallback check ke backend API jika server FastAPI aktif
        try {
          const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: rawUser, password: rawPass })
          });
          if (resp.ok) {
            const data = await resp.json();
            const userObj = {
              username: data.username,
              name: data.username,
              loginTime: Date.now()
            };
            setLoggedUser(userObj, rememberInput ? rememberInput.checked : true);
            if (gate) gate.classList.add('hidden');
            updateAuthUI(userObj);
            startTerminal();
            showToast(`Selamat datang, ${data.username}! 🚀`, '✅');
            return;
          }
        } catch (apiErr) {
          // Static serverless mode fallback
        }

        if (errorEl && errorText) {
          errorText.textContent = 'Username atau password salah!';
          errorEl.style.display = 'flex';
          // Trigger shake animation
          errorEl.classList.remove('login-error');
          void errorEl.offsetWidth; // re-flow
          errorEl.classList.add('login-error');
        }
        if (passwordInput) {
          passwordInput.value = '';
          passwordInput.focus();
        }
      }
    });
  }
}

// App Initialization Gate
window.addEventListener('DOMContentLoaded', () => {
  initAuth();
});

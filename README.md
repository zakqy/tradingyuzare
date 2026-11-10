# ⚡ YUZARE Real-Time Trading Terminal

Website dan Indikator Real-Time Khusus untuk **XAUUSD (Gold)** & **BTCUSD (Bitcoin)**, serta Multi-Timeframe dari **1 Menit (Scalping)** hingga **Weekly (Swing)**.

---

## 🌟 6 Fitur Utama Sesuai Permintaan

### 01. Pending Zone (Area Potensial Masa Depan)
- Area potensial support, resistance, dan order blocks digambar **di sebelah kanan chart (future space) sebelum harga tiba**.
- Memberikan waktu yang leluasa untuk mempersiapkan rencana entry (Buy Limit / Sell Limit).
- Terdapat label visual `pending buy` (warna hijau) dan `pending sell` (warna merah) lengkap dengan jarak pips / poin secara real-time.

### 02. Dual Signal (BUY & SELL Independen)
- Sinyal **BUY** dan **SELL** berjalan secara terpisah dan independen tanpa saling menimpa atau membatalkan posisi yang sedang aktif.
- Sangat cocok untuk scalper multi-orderflow maupun trader hedging.
- Setiap posisi BUY dan SELL memiliki kartu monitor terpisah di panel sidebar kanan.

### 03. TP1 · TP2 · TP3 · SL Otomatis
- Begitu sinyal terkonfirmasi, level keluar langsung digambar otomatis pada chart:
  - **SL (Stop Loss)**: Berbasis Swing Structure + Volatilitas ATR.
  - **TP1**: Risk/Reward ~1:1.2 (Target Scalping awal & pengamanan Breakeven).
  - **TP2**: Risk/Reward ~1:2.2 (Target Swing medium).
  - **TP3**: Risk/Reward ~1:3.8 (Target Runner maksimal).
- Dilengkapi status tracking otomatis (*ACTIVE*, *TP1 HIT ✓*, *TP2 HIT ✓*, *TP3 HIT 🎯*, *SL HIT*).

### 04. Zero Repaint (Terkunci Setelah Bar Close)
- Sinyal dihitung dan dikunci secara permanen begitu candlestick selesai/close (`bar close confirmation`).
- Apa yang Anda lihat di masa lalu tidak akan pernah berpindah, bergeser, atau hilang di kemudian hari.

### 05. Semua Timeframe (1m s/d Weekly)
- **1m & 5m**: Mode Scalping presisi tinggi dengan respon cepat.
- **15m & 30m**: Mode Intraday momentum.
- **1H, 4H, 1D, 1W**: Mode Swing trading terstruktur.
- Logika adaptif secara dinamis mengikuti rentang ATR setiap timeframe.

### 06. Dioptimalkan untuk XAUUSD & BTCUSD
- Didesain khusus mengantisipasi karakteristik pergerakan Gold (XAUUSD) dan Bitcoin (BTCUSD) yang memiliki volatilitas tinggi dan liquidity sweep.
- Dapat juga digunakan untuk pair lain seperti ETHUSD, SOLUSD, EURUSD, dan GBPUSD.
- Dilengkapi fitur **MT5 Sync Calibration** untuk menyamakan harga secara presisi dengan chart MT5 broker Anda.

---

## 🚀 Cara Menjalankan Website Terminal

### Cara 1: Menggunakan File `run.bat` (Paling Mudah)
Cukup **double-click file `run.bat`** di folder ini:
1. Server lokal akan otomatis menyala di background.
2. Browser akan terbuka otomatis ke alamat: **`http://127.0.0.1:8000`**

### Cara 2: Menjalankan via Terminal / CMD
```bash
py -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```
Buka browser dan akses: `http://127.0.0.1:8000`

### Cara 3: Akses Live GitHub Pages (Tanpa Perlu Instalasi)
Buka langsung di browser:
👉 **`https://zakqy.github.io/tradingyuzare/`**

---

## 📊 Penggunaan di TradingView (Pine Script v5)

Selain website real-time lokal, indikator ini juga disediakan dalam format **TradingView Pine Script v5**:
1. Buka website Anda di `http://127.0.0.1:8000` atau via GitHub Pages.
2. Klik tombol **"📋 Copy Pine Script"** di pojok kanan atas.
3. Buka [TradingView.com](https://www.tradingview.com) dan buka chart apa saja.
4. Di bagian bawah layar TradingView, klik tab **Pine Editor**.
5. Paste kodenya lalu klik **"Add to Chart"**.
6. File sumber juga tersimpan di folder `pinescript/YUZARE_Indicator.pine`.

---

## 🎨 Tampilan dan Skema Warna
- **Background**: Modern Dark Terminal (`#0b0e14`).
- **Candle Bullish**: Vivid Green (`#00c853`).
- **Candle Bearish**: Vivid Red (`#f23645`).
- **Pending Sell**: Red / Maroon rounded tag di area resistance masa depan.
- **Pending Buy**: Green / Emerald rounded tag di area support masa depan.
- **Audio Sound Effects**: Dilengkapi audio synthesizer Web Audio API untuk notifikasi BUY, SELL, Pending Alert, dan TP Hit.


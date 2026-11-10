//+------------------------------------------------------------------+
//|                                                     TRXC_QRR.mq5 |
//|                                  Copyright 2026, TRXC QRR Engine |
//|                                             https://127.0.0.1    |
//+------------------------------------------------------------------+
#property copyright   "TRXC QRR"
#property link        "https://127.0.0.1"
#property version     "1.00"
#property description "TRXC QRR - Quantum Range Reaction Indicator [Zero Repaint]"
#property description "Dual Signal | Pending Zones | TP1-3 & SL Auto | Multi-TF"
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   2

//--- Plot Buy Arrow
#property indicator_label1  "TRXC BUY"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLimeGreen
#property indicator_width1  2

//--- Plot Sell Arrow
#property indicator_label2  "TRXC SELL"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrCrimson
#property indicator_width2  2

//--- Inputs
input group "=== TRXC QRR Engine Parameters ==="
input int      InpAtrPeriod     = 14;          // ATR Period
input double   InpAtrMult       = 1.5;         // ATR Multiplier for SL
input int      InpFastEma       = 9;           // Fast EMA
input int      InpSlowEma       = 21;          // Slow EMA

input group "=== 01. Pending Zones (Future Projection) ==="
input bool     InpShowPending   = true;        // Tampilkan Pending Zones
input int      InpPivotLookback = 6;           // Pivot Lookback
input int      InpForwardBars   = 25;          // Proyeksi ke Masa Depan (Bars)

input group "=== 02 & 03. Dual Signal & TP/SL Multipliers ==="
input bool     InpEnableBuy     = true;        // Aktifkan Sinyal BUY
input bool     InpEnableSell    = true;        // Aktifkan Sinyal SELL
input double   InpRR_TP1        = 1.2;         // Rasio TP1
input double   InpRR_TP2        = 2.2;         // Rasio TP2
input double   InpRR_TP3        = 3.8;         // Rasio TP3
input bool     InpDrawTPSLLines = true;        // Gambar Garis TP & SL

input group "=== Alert Settings ==="
input bool     InpAlertAudio    = true;        // Mainkan Suara Alert
input bool     InpAlertPopup    = true;        // Tampilkan Popup Alert
input bool     InpAlertPush     = false;       // Kirim Push Notification ke HP

//--- Indicator Buffers
double BufferBuy[];
double BufferSell[];
double BufferAtr[];
double BufferEmaFast[];
double BufferEmaSlow[];

//--- Indicator Handles
int handleAtr;
int handleEmaFast;
int handleEmaSlow;

datetime lastBuyTime = 0;
datetime lastSellTime = 0;

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
{
   // Buffers mapping
   SetIndexBuffer(0, BufferBuy, INDICATOR_DATA);
   SetIndexBuffer(1, BufferSell, INDICATOR_DATA);
   
   PlotIndexSetInteger(0, PLOT_ARROW, 233); // Wingdings arrow up
   PlotIndexSetInteger(1, PLOT_ARROW, 234); // Wingdings arrow down

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, 0.0);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, 0.0);

   // Indicators
   handleAtr = iATR(_Symbol, _Period, InpAtrPeriod);
   handleEmaFast = iMA(_Symbol, _Period, InpFastEma, 0, MODE_EMA, PRICE_CLOSE);
   handleEmaSlow = iMA(_Symbol, _Period, InpSlowEma, 0, MODE_EMA, PRICE_CLOSE);

   if(handleAtr == INVALID_HANDLE || handleEmaFast == INVALID_HANDLE || handleEmaSlow == INVALID_HANDLE)
   {
      Print("Gagal menginisialisasi indikator handle di MT5.");
      return(INIT_FAILED);
   }

   // Styling chart candles to Green / Red
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, StringToColor("#00C853")); // Green
   ChartSetInteger(0, CHART_COLOR_CHART_UP,    StringToColor("#00C853"));
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, StringToColor("#F23645")); // Red
   ChartSetInteger(0, CHART_COLOR_CHART_DOWN,  StringToColor("#F23645"));
   ChartSetInteger(0, CHART_COLOR_BACKGROUND,  StringToColor("#0B0E14")); // Dark
   ChartSetInteger(0, CHART_COLOR_FOREGROUND,  StringToColor("#8B949E"));

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   if(rates_total < InpSlowEma + 20) return(0);

   // Zero Repaint: hitung hanya bar yang SUDAH TERTUTUP (i <= rates_total - 2)
   int start = prev_calculated - 1;
   if(start < InpSlowEma + 10) start = InpSlowEma + 10;

   double atr[];
   double emaFast[];
   double emaSlow[];
   ArraySetAsSeries(atr, false);
   ArraySetAsSeries(emaFast, false);
   ArraySetAsSeries(emaSlow, false);

   if(CopyBuffer(handleAtr, 0, 0, rates_total, atr) <= 0) return(0);
   if(CopyBuffer(handleEmaFast, 0, 0, rates_total, emaFast) <= 0) return(0);
   if(CopyBuffer(handleEmaSlow, 0, 0, rates_total, emaSlow) <= 0) return(0);

   // Evaluasi Sinyal Zero Repaint
   for(int i = start; i < rates_total - 1; i++)
   {
      BufferBuy[i] = 0.0;
      BufferSell[i] = 0.0;

      double curAtr = atr[i] > 0 ? atr[i] : _Point * 10;
      bool isBullCandle = close[i] > open[i];
      bool isBearCandle = close[i] < open[i];

      // QRR Bullish Condition
      bool bullCross = emaFast[i] > emaSlow[i] && (emaFast[i - 1] <= emaSlow[i - 1] || (close[i] > close[i - 1] + 0.3 * curAtr));
      bool bullImpulse = isBullCandle && (close[i] - open[i] > 0.3 * (high[i] - low[i] + _Point));

      // QRR Bearish Condition
      bool bearCross = emaFast[i] < emaSlow[i] && (emaFast[i - 1] >= emaSlow[i - 1] || (close[i] < close[i - 1] - 0.3 * curAtr));
      bool bearImpulse = isBearCandle && (open[i] - close[i] > 0.3 * (high[i] - low[i] + _Point));

      // Sinyal BUY (Zero Repaint)
      if(InpEnableBuy && bullCross && bullImpulse)
      {
         BufferBuy[i] = low[i] - 0.3 * curAtr;
         if(i == rates_total - 2 && time[i] != lastBuyTime)
         {
            lastBuyTime = time[i];
            TriggerAlert("TRXC QRR: BUY Sinyal Terkonfirmasi pada " + _Symbol + " @ " + DoubleToString(close[i], _Digits));
            if(InpDrawTPSLLines) DrawTPSLLines(true, time[i], close[i], low[i], curAtr);
         }
      }

      // Sinyal SELL (DUAL SIGNAL: Independen!)
      if(InpEnableSell && bearCross && bearImpulse)
      {
         BufferSell[i] = high[i] + 0.3 * curAtr;
         if(i == rates_total - 2 && time[i] != lastSellTime)
         {
            lastSellTime = time[i];
            TriggerAlert("TRXC QRR: SELL Sinyal Terkonfirmasi pada " + _Symbol + " @ " + DoubleToString(close[i], _Digits));
            if(InpDrawTPSLLines) DrawTPSLLines(false, time[i], close[i], high[i], curAtr);
         }
      }
   }

   // Update Pending Zones di masa depan (Feature 01)
   if(InpShowPending && rates_total > 50)
   {
      UpdatePendingZones(rates_total, time, high, low, close, open, atr[rates_total - 1]);
   }

   return(rates_total);
}

//+------------------------------------------------------------------+
//| Menggambar Garis TP1, TP2, TP3 dan SL                            |
//+------------------------------------------------------------------+
void DrawTPSLLines(bool isBuy, datetime t, double entry, double swingExtreme, double curAtr)
{
   string prefix = isBuy ? "TRXC_BUY_" : "TRXC_SELL_";
   datetime tEnd = t + PeriodSeconds() * 20;

   double risk = MathMax(curAtr * InpAtrMult, MathAbs(entry - swingExtreme));
   double sl   = isBuy ? (entry - risk) : (entry + risk);
   double tp1  = isBuy ? (entry + risk * InpRR_TP1) : (entry - risk * InpRR_TP1);
   double tp2  = isBuy ? (entry + risk * InpRR_TP2) : (entry - risk * InpRR_TP2);
   double tp3  = isBuy ? (entry + risk * InpRR_TP3) : (entry - risk * InpRR_TP3);

   color colTP = isBuy ? StringToColor("#00E5FF") : StringToColor("#FF1744");
   color colSL = clrRed;

   CreateLine(prefix + "SL", t, sl, tEnd, sl, colSL, STYLE_DASH);
   CreateLine(prefix + "TP1", t, tp1, tEnd, tp1, colTP, STYLE_DASH);
   CreateLine(prefix + "TP2", t, tp2, tEnd, tp2, colTP, STYLE_DASH);
   CreateLine(prefix + "TP3", t, tp3, tEnd, tp3, colTP, STYLE_SOLID, 2);
}

void CreateLine(string name, datetime t1, double p1, datetime t2, double p2, color c, ENUM_LINE_STYLE style, int width = 1)
{
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
}

//+------------------------------------------------------------------+
//| Proyeksi Pending Zones ke Kanan Chart (Masa Depan)              |
//+------------------------------------------------------------------+
void UpdatePendingZones(int total, const datetime &time[], const double &high[], const double &low[], const double &close[], const double &open[], double curAtr)
{
   double curPrice = close[total - 1];
   datetime tFutureStart = time[total - 1] + PeriodSeconds() * 3;
   datetime tFutureEnd   = time[total - 1] + PeriodSeconds() * InpForwardBars;

   int foundSells = 0;
   int foundBuys = 0;

   for(int i = total - InpPivotLookback - 1; i > total - 120 && i > InpPivotLookback; i--)
   {
      if(foundSells >= 3 && foundBuys >= 3) break;

      // Pivot High -> Pending Sell
      bool isPH = true;
      for(int k = 1; k <= InpPivotLookback; k++)
      {
         if(high[i] < high[i - k] || high[i] < high[i + k]) { isPH = false; break; }
      }
      if(isPH && high[i] > curPrice && foundSells < 3)
      {
         foundSells++;
         string name = "TRXC_PZ_SELL_" + IntegerToString(foundSells);
         ObjectDelete(0, name);
         ObjectCreate(0, name, OBJ_RECTANGLE, 0, tFutureStart, high[i] + 0.15 * curAtr, tFutureEnd, high[i]);
         ObjectSetInteger(0, name, OBJPROP_COLOR, StringToColor("#D50000"));
         ObjectSetInteger(0, name, OBJPROP_BGCOLOR, StringToColor("#4A151B"));
         ObjectSetInteger(0, name, OBJPROP_FILL, true);

         string txtName = "TRXC_PZ_LBL_SELL_" + IntegerToString(foundSells);
         ObjectDelete(0, txtName);
         ObjectCreate(0, txtName, OBJ_TEXT, 0, tFutureStart + PeriodSeconds() * 4, high[i]);
         ObjectSetString(0, txtName, OBJPROP_TEXT, "pending sell " + DoubleToString(high[i], _Digits));
         ObjectSetInteger(0, txtName, OBJPROP_COLOR, StringToColor("#FF8A80"));
      }

      // Pivot Low -> Pending Buy
      bool isPL = true;
      for(int k = 1; k <= InpPivotLookback; k++)
      {
         if(low[i] > low[i - k] || low[i] > low[i + k]) { isPL = false; break; }
      }
      if(isPL && low[i] < curPrice && foundBuys < 3)
      {
         foundBuys++;
         string name = "TRXC_PZ_BUY_" + IntegerToString(foundBuys);
         ObjectDelete(0, name);
         ObjectCreate(0, name, OBJ_RECTANGLE, 0, tFutureStart, low[i], tFutureEnd, low[i] - 0.15 * curAtr);
         ObjectSetInteger(0, name, OBJPROP_COLOR, StringToColor("#00C853"));
         ObjectSetInteger(0, name, OBJPROP_BGCOLOR, StringToColor("#0D381E"));
         ObjectSetInteger(0, name, OBJPROP_FILL, true);

         string txtName = "TRXC_PZ_LBL_BUY_" + IntegerToString(foundBuys);
         ObjectDelete(0, txtName);
         ObjectCreate(0, txtName, OBJ_TEXT, 0, tFutureStart + PeriodSeconds() * 4, low[i]);
         ObjectSetString(0, txtName, OBJPROP_TEXT, "pending buy " + DoubleToString(low[i], _Digits));
         ObjectSetInteger(0, txtName, OBJPROP_COLOR, StringToColor("#B9F6CA"));
      }
   }
}

//+------------------------------------------------------------------+
//| Trigger Notifikasi Audio, Popup & Push                           |
//+------------------------------------------------------------------+
void TriggerAlert(string msg)
{
   if(InpAlertAudio) PlaySound("alert.wav");
   if(InpAlertPopup) Alert(msg);
   if(InpAlertPush)  SendNotification(msg);
}

//+------------------------------------------------------------------+
//| Deinitialization function                                        |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "TRXC_");
   IndicatorRelease(handleAtr);
   IndicatorRelease(handleEmaFast);
   IndicatorRelease(handleEmaSlow);
}
//+------------------------------------------------------------------+


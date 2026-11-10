//+------------------------------------------------------------------+
//|                                              MT5_Live_Bridge.mq5 |
//|                                  Copyright 2026, TRXC QRR Engine |
//|         Jembatan Real-Time Feed dari MetaTrader 5 ke Web Terminal|
//+------------------------------------------------------------------+
#property copyright "TRXC QRR"
#property link      "http://127.0.0.1:8000"
#property version   "1.00"
#property description "EA Bridge untuk mengirim harga tick real-time dari MT5 ke Web Terminal TRXC QRR"
#property description "Pastikan 'http://127.0.0.1:8000' diizinkan di Tools -> Options -> Expert Advisors -> Allow WebRequest"

input group "=== Konfigurasi Web Terminal ==="
input string   InpServerUrl     = "http://127.0.0.1:8000/api/mt5_tick"; // URL Server Web Terminal
input string   InpSymbolMap     = "XAUUSD";                              // Target Symbol di Web
input int      InpThrottleMs    = 250;                                   // Throttle Update (ms)

datetime lastSendTime = 0;
ulong    lastTickMs = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("TRXC MT5 Bridge aktif pada symbol: ", _Symbol);
   Print("Mengirim harga langsung ke Web Terminal: ", InpServerUrl);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   ulong nowMs = GetTickCount64();
   if(nowMs - lastTickMs < (ulong)InpThrottleMs) return;
   lastTickMs = nowMs;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   // Buat payload JSON
   string json = StringFormat("{\"symbol\":\"%s\",\"bid\":%.2f,\"ask\":%.2f,\"time\":%d}",
                              InpSymbolMap, tick.bid, tick.ask, (long)tick.time);

   char postData[];
   char result[];
   string resultHeaders;
   StringToCharArray(json, postData, 0, WHOLE_ARRAY, CP_UTF8);

   string headers = "Content-Type: application/json\r\n";
   int res = WebRequest("POST", InpServerUrl, headers, 1000, postData, result, resultHeaders);
   if(res == -1)
   {
      // Jika WebRequest gagal, kemungkinan URL belum dimasukkan ke Allow WebRequest
      static bool warned = false;
      if(!warned)
      {
         Print("Peringatan: Gagal mengirim WebRequest ke ", InpServerUrl);
         Print("Silakan tambahkan 'http://127.0.0.1:8000' di Tools -> Options -> Expert Advisors -> WebRequest");
         warned = true;
      }
   }
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("TRXC MT5 Bridge dimatikan.");
}


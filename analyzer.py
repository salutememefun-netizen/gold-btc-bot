# Bahagian atas analyzer.py
import os

# Pastikan tiada ruang sebelum atau selepas nama variable
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip() 

# Jika API Key masih kosong, bot akan print error di log Railway
if not FINNHUB_API_KEY:
    print("❌ CRITICAL ERROR: FINNHUB_API_KEY tidak ditemui di Environment Variables!")

import os

print("=== SEMAK RAILWAY VARIABLES ===")
print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")
print(f"BOT_TOKEN: {os.getenv('BOT_TOKEN')}")
print(f"TELEGRAM_BOT_TOKEN: {os.getenv('TELEGRAM_BOT_TOKEN')}")
print("================================")

# Senaraikan SEMUA variable yang ada
print("\n=== SEMUA VARIABLE YANG ADA ===")
for key, value in os.environ.items():
    if 'DB' in key.upper() or 'TOKEN' in key.upper() or 'URL' in key.upper():
        print(f"{key}: {value[:10]}...")  # Show first 10 chars saja

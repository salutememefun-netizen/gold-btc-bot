import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from io import BytesIO
from helpers import get_btc_historical, get_gold_historical

def create_price_chart(asset_name: str, prices: list, days: int = 30) -> BytesIO:
    """
    Buat carta harga dan return sebagai BytesIO (gambar).
    
    Args:
        asset_name: "BTC" atau "GOLD"
        prices: Senarai harga historis
        days: Bilangan hari untuk chart
    
    Returns:
        BytesIO object (gambar yang boleh dihantar ke Telegram)
    """
    if not prices or len(prices) < 2:
        return None

    # Buat senarai tarikh (dari 'days' hari lepas hingga hari ini)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = [start_date + timedelta(days=i) for i in range(len(prices))]

    # Setup figure dan style
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))

    # Tentukan warna berdasarkan aset
    if asset_name == "BTC":
        line_color = '#F7931A'  # Bitcoin orange
        fill_color = '#F7931A'
        title_text = "Bitcoin (BTC) - 30 Hari Terakhir"
    else:  # GOLD
        line_color = '#FFD700'  # Gold yellow
        fill_color = '#FFD700'
        title_text = "Emas (XAU) - 30 Hari Terakhir"

    # Plot garis harga
    ax.plot(dates, prices, color=line_color, linewidth=2.5, label=f'{asset_name} Price')
    ax.fill_between(dates, prices, alpha=0.2, color=fill_color)

    # Format X-axis (tarikh)
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=45, ha='right')

    # Format Y-axis (harga)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Labels dan title
    ax.set_title(title_text, fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Tarikh', fontsize=10)
    ax.set_ylabel('Harga (USD)', fontsize=10)
    ax.grid(True, alpha=0.2)
    ax.legend(loc='upper left')

    # Tight layout
    plt.tight_layout()

    # Simpan ke BytesIO (dalam memori, bukan file)
    img_bytes = BytesIO()
    plt.savefig(img_bytes, format='png', dpi=100, bbox_inches='tight')
    img_bytes.seek(0)
    plt.close()

    return img_bytes

def get_btc_chart() -> BytesIO:
    """Dapatkan carta BTC"""
    prices = get_btc_historical(30)
    if prices:
        return create_price_chart("BTC", prices, 30)
    return None

def get_gold_chart() -> BytesIO:
    """Dapatkan carta GOLD"""
    prices = get_gold_historical(30)
    if prices:
        return create_price_chart("GOLD", prices, 30)
    return None

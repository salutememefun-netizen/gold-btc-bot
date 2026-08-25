        # --- Entry, SL, TP (BUY dan SELL BERBEZA) ---
        risk  = 0.005
        ratio = 2.0

        # BUY zone
        if fvg_b:
            buy_entry = fvg_b[0]
        else:
            buy_entry = round(price * 0.998, 2)  # 0.2% bawah harga semasa
        buy_sl = round(buy_entry * (1 - risk), 2)
        buy_tp = round(buy_entry + ((buy_entry - buy_sl) * ratio), 2)

        # SELL zone
        if fvg_s:
            sell_entry = fvg_s[1]
        else:
            sell_entry = round(price * 1.002, 2)  # 0.2% atas harga semasa
        sell_sl = round(sell_entry * (1 + risk), 2)
        sell_tp = round(sell_entry - ((sell_sl - sell_entry) * ratio), 2)

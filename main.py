from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os, re

# --- Ayarlar ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
UNIT_TL = int(os.getenv("UNIT_TL", "50"))  # 1u = 50 TL (min kupon 50 TL)
MIN_ODDS_DEFAULT = 1.60                    # min öneri oranı
TZ = os.getenv("TZ", "Europe/Istanbul")    # Railway Env'de de ayarla

HELP_TEXT = (
    "Canlı Fırsat Sistemi Botu aktif ✅\n"
    f"• 1u = {UNIT_TL} TL (min kupon 50 TL)\n"
    "• Sadece iddaa pazar isimlendirmesiyle öneri verir.\n\n"
    "Kullanım:\n"
    "⚽ FUTBOL (F1/F2): /f min=72 xgA=1.35 xgB=0.40 shotsA=14 shotsB=6 possA=66 possB=34 attA=80 attB=35\n"
    "🎾 TENİS (T1/T2): /t set=2 game=8 a1st=74 a1stwon=78 a2ndwon=58 b1st=60 b1stwon=62 b2ndwon=41 bpa=3/4 bpb=1/5 last10=7-3\n"
    "Çıktı: AL / BEKLE / UZAK DUR + [pazar] + min oran + stake (1u={} TL)".format(UNIT_TL)
)

def parse_kv(text: str):
    # "key=value" çiftlerini sözlüğe çevirir (virgül/boşluk ayırıcı)
    pairs = re.findall(r'(\w+)\s*=\s*([^\s,]+)', text)
    d = {}
    for k, v in pairs:
        d[k.lower()] = v
    return d

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)

# ---------- FUTBOL TETİK (F1/F2) ----------
def football_trigger(d):
    minute = int(float(d.get("min", 0)))
    xgA = float(d.get("xga", 0)); xgB = float(d.get("xgb", 0))
    shotsA = int(float(d.get("shotsa", 0))); shotsB = int(float(d.get("shotsb", 0)))
    possA = int(float(d.get("possa", 50))); possB = int(float(d.get("possb", 50)))
    attA = int(float(d.get("atta", 0))); attB = int(float(d.get("attb", 0)))  # dangerous attacks

    # F1: 60–75.dk yüksek xG farkı + şut farkı
    F1 = (60 <= minute <= 75) and (abs(xgA - xgB) >= 0.80) and (abs(shotsA - shotsB) >= 5)

    # F2: 70–85.dk tek yön baskı (possession + tehlikeli atak + şut farkı)
    F2 = (70 <= minute <= 85) and (
        (possA >= 65 and (attA - attB) >= 20 and (shotsA - shotsB) >= 5) or
        (possB >= 65 and (attB - attA) >= 20 and (shotsB - shotsA) >= 5)
    )

    if F1 or F2:
        # İddaa uyumlu hızlı pazar: ÜST 0.5 Gol
        market = "ÜST 0.5 Gol"
        min_odds = 1.55
        units = 1.0
        return ("AL", market, min_odds, units)

    return ("BEKLE" if minute <= 85 else "UZAK DUR", "-", MIN_ODDS_DEFAULT, 0)

# ---------- TENİS TETİK (T1/T2) ----------
def parse_frac(s):
    if "/" in s:
        a,b = s.split("/",1)
        try:
            a = float(a); b = float(b)
            return a,b,(a/b if b>0 else 0.0)
        except:
            return 0,0,0.0
    return 0,0,0.0

def tennis_trigger(d):
    a1st = int(float(d.get("a1st", 0))); a1won = int(float(d.get("a1stwon", 0)))
    b1st = int(float(d.get("b1st", 0))); b1won = int(float(d.get("b1stwon", 0)))
    bpa = d.get("bpa", "0/0"); bpb = d.get("bpb", "0/0")
    _,_,bpA = parse_frac(bpa); _,_,bpB = parse_frac(bpb)
    last10 = d.get("last10","0-0")
    try:
        lA,lB = map(int,last10.split("-",1))
    except:
        lA,lB = 0,0

    # T1: Servis Dominasyonu — (A veya B) 1st%>=70 & 1stWon>=70 & last10>=7
    T1A = (a1st>=70 and a1won>=70 and lA>=7)
    T1B = (b1st>=70 and b1won>=70 and lB>=7)

    # T2: Clutch BP — BP conversion>=0.60 & last10>=6
    T2A = (bpA>=0.60 and lA>=6)
    T2B = (bpB>=0.60 and lB>=6)

    if T1A or T2A:
        return ("AL", "Maç Sonucu (1. Oyuncu)", 1.60, 1.0)
    if T1B or T2B:
        return ("AL", "Maç Sonucu (2. Oyuncu)", 1.60, 1.0)

    return ("BEKLE", "-", MIN_ODDS_DEFAULT, 0)

# ---------- Handler'lar ----------
async def handle_f(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args_text = " ".join(context.args)
    d = parse_kv(args_text)
    decision, market, min_odds, units = football_trigger(d)
    if decision == "AL":
        msg = f"AL + {market} + min {min_odds:.2f} + {units:.1f}u ({int(units*UNIT_TL)} TL)"
    elif decision == "BEKLE":
        msg = "BEKLE + uygun pazar/eşik bekleniyor"
    else:
        msg = "UZAK DUR + veri/EV yetersiz"
    await update.message.reply_text(msg)

async def handle_t(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args_text = " ".join(context.args)
    d = parse_kv(args_text)
    decision, market, min_odds, units = tennis_trigger(d)
    if decision == "AL":
        msg = f"AL + {market} + min {min_odds:.2f} + {units:.1f}u ({int(units*UNIT_TL)} TL)"
    elif decision == "BEKLE":
        msg = "BEKLE + uygun pazar/eşik bekleniyor"
    else:
        msg = "UZAK DUR + veri/EV yetersiz"
    await update.message.reply_text(msg)

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN tanımlı değil.")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("f", handle_f))
    app.add_handler(CommandHandler("t", handle_t))
    app.run_polling()

if __name__ == "__main__":
    main()

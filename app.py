import os
import runpy
# для bhost

ROOT = os.path.dirname(os.path.abspath(__file__))
BOT_FILE = os.path.join(ROOT, "bot.py")

if not os.path.isfile(BOT_FILE):
    raise FileNotFoundError(f"bot.py not found at {BOT_FILE}")

runpy.run_path(BOT_FILE, run_name="__main__")

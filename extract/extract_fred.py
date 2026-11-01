import json
import os
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("FRED_API_KEY")
if not API_KEY:
    raise SystemExit("FRED_API_KEY not found. Check your .env file.")

SERIES_ID = "MORTGAGE30US"
URL = "https://api.stlouisfed.org/fred/series/observations"

response = requests.get(
    URL,
    params={"series_id": SERIES_ID, "api_key": API_KEY, "file_type": "json"},
    timeout=30,
)
response.raise_for_status()  # stops loudly on HTTP errors
data = response.json()


PROJECT_ROOT = Path(__file__).resolve().parent.parent
out_dir = PROJECT_ROOT / "raw" / "fred"
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / f"{SERIES_ID}_{date.today()}.json"
out_file.write_text(json.dumps(data), encoding="utf-8")

print(f"Saved {len(data['observations'])} observations to {out_file}")
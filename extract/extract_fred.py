import json
import os
import sys
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("FRED_API_KEY")
if not API_KEY:
    raise SystemExit("FRED_API_KEY not found. Check your .env file.")

URL = "https://api.stlouisfed.org/fred/series/observations"

# Series IDs verified against the FRED API on 2026-11-01 (see docs/report_spec.md)
SERIES_IDS = [
    # Mortgage rates: Freddie Mac weekly averages
    "MORTGAGE30US",   # 30-year fixed
    "MORTGAGE15US",   # 15-year fixed
    # Mortgage rates: Optimal Blue daily indexes by loan type (from 2017)
    "OBMMIC30YF",     # 30-year fixed conforming
    "OBMMIC15YF",     # 15-year fixed conforming
    "OBMMIFHA30YF",   # 30-year fixed FHA
    "OBMMIVA30YF",    # 30-year fixed VA
    "OBMMIUSDA30YF",  # 30-year fixed USDA
    "OBMMIJUMBO30YF", # 30-year fixed jumbo
    "DGS10",          # 10-year Treasury yield (daily), for the mortgage rate spread
    # Home prices and sales
    "CSUSHPISA",      # S&P Cotality Case-Shiller U.S. National Home Price Index
    "USSTHPI",        # FHFA all-transactions house price index
    "MSPUS",          # median sales price of new houses sold
    "ASPUS",          # average sales price of new houses sold
    "HSN1F",          # new one-family houses sold
    "MSACSR",         # monthly supply of new houses
    "EXHOSLUSM495S",  # existing home sales (FRED keeps only the latest ~13 months)
    # Listings: Realtor.com housing inventory (from 2016)
    "MEDLISPRIUS",    # median listing price
    "MEDLISPRIPERSQUFEEUS",  # median listing price per square foot
    "MEDSQUFEEUS",    # median home size in square feet
    "ACTLISCOUUS",    # active listing count
    "NEWLISCOUUS",    # new listing count
    "PENLISCOUUS",    # pending listing count
    "PRIREDCOUUS",    # price reduced count
    "MEDDAYONMARUS",  # median days on market
    # New supply: the construction pipeline
    "PERMIT",         # building permits, total
    "PERMIT1",        # building permits, single-family
    "AUTHNOTTSA",     # permitted but not yet started
    "HOUST",          # housing starts, total
    "HOUST1F",        # housing starts, single-family
    "UNDCONTSA",      # under construction
    "COMPUTSA",       # completed
    # Rentals, ownership, and vacancy
    "CUSR0000SEHA",   # CPI rent of primary residence
    "CUSR0000SAH1",   # CPI shelter
    "CUSR0000SEHC",   # CPI owners' equivalent rent
    "RRVRUSQ156N",    # rental vacancy rate
    "RHVRUSQ156N",    # homeowner vacancy rate
    "EVACANTUSQ176N", # vacant housing units
    "RSAHORUSQ156S",  # homeownership rate
    # Affordability, credit risk, and the economy
    "MEHOINUSA672N",  # real median household income (annual)
    "MDSP",           # mortgage debt service payments as % of disposable income
    "DRSFRMACBS",     # single-family mortgage delinquency rate
    "UNRATE",         # unemployment rate
    "POPTHM",         # population
]

out_dir = PROJECT_ROOT / "raw" / "fred"
out_dir.mkdir(parents=True, exist_ok=True)

failed = []
for series_id in SERIES_IDS:
    try:
        response = requests.get(
            URL,
            params={"series_id": series_id, "api_key": API_KEY, "file_type": "json"},
            timeout=30,
        )
        response.raise_for_status()  # stops loudly on HTTP errors
        data = response.json()
    except requests.RequestException as e:
        # Keep going so one bad series doesn't block the rest, but remember it.
        # Error messages include the request URL, so hide the API key before printing.
        print(f"FAILED {series_id}: {str(e).replace(API_KEY, '***')}")
        failed.append(series_id)
        continue

    out_file = out_dir / f"{series_id}_{date.today()}.json"
    out_file.write_text(json.dumps(data), encoding="utf-8")
    print(f"Saved {len(data['observations']):>6} observations to {out_file.name}")

if failed:
    # A non-zero exit tells the pipeline wrapper not to run the later steps
    sys.exit(f"{len(failed)} of {len(SERIES_IDS)} series failed: {', '.join(failed)}")

print(f"All {len(SERIES_IDS)} series saved.")

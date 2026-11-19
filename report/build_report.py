"""Build the "pick a ZIP, get a report" housing market report (v1).

Reads the dbt marts in us_home_data.duckdb, renders an HTML report with
charts, and prints it to PDF with a Chromium browser in headless mode
(Microsoft Edge ships with Windows; Google Chrome also works).

Usage, from the project root:
    .venv\\Scripts\\python.exe report\\build_report.py --zip 77494
    .venv\\Scripts\\python.exe report\\build_report.py --state TX
    .venv\\Scripts\\python.exe report\\build_report.py --us
Add --html-only to skip the PDF.

Output goes to output/reports/ (not tracked in Git: reports contain
Zillow-derived figures, which are shared only deliberately, with attribution).
"""

import argparse
import io
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import duckdb
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from charts import line_chart

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "us_home_data.duckdb"
TEMPLATE_DIR = PROJECT_ROOT / "report" / "templates"
OUTPUT_DIR = PROJECT_ROOT / "output" / "reports"

BROWSER_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]

# Fixed chart color slot per geography (see charts.py)
SLOT = {"zip": 0, "state": 1, "national": 2}

MINUS = "\u2212"  # typographic minus sign
DASH = "\u2014"   # shown for missing values


# --- Database helpers -------------------------------------------------------

def rows(con, sql, params=None):
    """Run a query and return a list of dicts."""
    cursor = con.execute(sql, params or [])
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, r)) for r in cursor.fetchall()]


def one(con, sql, params=None, error="Query returned no rows"):
    """Run a query that must return exactly one row."""
    result = rows(con, sql, params)
    if len(result) != 1:
        raise SystemExit(f"{error} ({len(result)} rows found)")
    return result[0]


def maybe_one(con, sql, params=None):
    result = rows(con, sql, params)
    return result[0] if result else None


# --- Formatting filters for the template -----------------------------------

def fmt_money(v):
    return DASH if v is None else f"${v:,.0f}"


def fmt_signed_pct(v, decimals=1):
    if v is None:
        return DASH
    text = f"{abs(v):.{decimals}f}%"
    return ("+" if v > 0 else MINUS if v < 0 else "") + text


def fmt_signed_pts(v, decimals=2):
    if v is None:
        return DASH
    text = f"{abs(v):.{decimals}f}"
    return ("+" if v > 0 else MINUS if v < 0 else "") + text + " pts"


def fmt_rate(v, decimals=2):
    return DASH if v is None else f"{v:.{decimals}f}%"


def fmt_num(v, decimals=0):
    return DASH if v is None else f"{v:,.{decimals}f}"


def fmt_month(d):
    return DASH if d is None else d.strftime("%B %Y")


def fmt_day(d):
    return DASH if d is None else f"{d.strftime('%b')} {d.day}, {d.year}"


# --- Data gathering ---------------------------------------------------------

def region_figures(con, region_id):
    """Latest home value, rent, payment, and forecast for one Zillow region."""
    values = one(con, "select * from marts.home_values_rents_current where region_id = ?",
                 [region_id], error=f"No current values for region {region_id}")
    afford = maybe_one(con, "select * from marts.affordability_current where region_id = ?",
                       [region_id])
    forecast = maybe_one(con, "select * from marts.home_value_forecast_current where region_id = ?",
                         [region_id])
    return {"values": values, "afford": afford or {}, "forecast": forecast or {}}


def trend(con, region_id, column, since):
    # Column names can't be ? parameters, so only known names are allowed
    if column not in ("typical_home_value", "typical_rent"):
        raise ValueError(f"Unexpected column {column!r}")
    data = rows(con, f"""
        select month_end_date, {column} as v
        from marts.fct_home_values_rents_monthly
        where region_id = ? and {column} is not null and month_end_date >= ?
        order by month_end_date
    """, [region_id, since])
    return [r["month_end_date"] for r in data], [r["v"] for r in data]


def years_before(d, years):
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - years, day=28)


def build_geographies(con, args):
    """Return the report's geographies in order: focus first, then state, then US."""
    us_row = one(con, "select * from marts.home_values_rents_current where geography_level = 'national'")
    us = {"level": "national", "name": "United States", "short": "US",
          "region_id": us_row["region_id"]}

    if args.us:
        return [us], {}

    if args.state:
        code = args.state.strip().upper()
        st = one(con, "select * from seeds.states where state_code = ?", [code],
                 error=f"Unknown state code {code!r}")
        state_row = one(con, """select * from marts.home_values_rents_current
                                where geography_level = 'state' and state_name = ?""",
                        [st["state_name"]], error=f"No Zillow data for {st['state_name']}")
        state = {"level": "state", "name": st["state_name"], "short": code,
                 "region_id": state_row["region_id"], "state_code": code}
        return [state, us], {}

    zip_code = args.zip.strip()
    z = one(con, "select * from marts.zip_comparison_current where zip_code = ?", [zip_code],
            error=f"No Zillow home value for ZIP {zip_code}")
    state_row = one(con, """select * from marts.home_values_rents_current
                            where geography_level = 'state' and state_name = ?""",
                    [z["state_name"]])
    zip_geo = {"level": "zip", "name": f"{zip_code} ({z['city']})", "short": zip_code,
               "region_id": z["region_id"]}
    state = {"level": "state", "name": z["state_name"], "short": z["state_code"],
             "region_id": state_row["region_id"], "state_code": z["state_code"]}
    return [zip_geo, state, us], z


def build_context(con, args):
    geos, zip_row = build_geographies(con, args)
    focus = geos[0]
    for g in geos:
        g.update(region_figures(con, g["region_id"]))

    focus_values = focus["values"]
    as_of = focus_values["home_value_as_of"]

    # Rank and context sentences
    rank = None
    if focus["level"] == "zip":
        rank = {
            "value_rank": zip_row["home_value_rank_in_state"],
            "zips_in_state": zip_row["zips_in_state"],
            "percentile_state": zip_row["home_value_percentile_in_state"],
            "percentile_us": zip_row["home_value_percentile_in_us"],
            "change_rank": zip_row["home_value_change_1y_rank_in_state"],
            "zips_with_change": zip_row["zips_in_state_with_change_1y"],
        }
    elif focus["level"] == "state":
        rank = one(con, """
            select value_rank, n from (
                select region_id,
                       rank() over (order by typical_home_value desc) as value_rank,
                       count(*) over () as n
                from marts.home_values_rents_current
                where geography_level = 'state' and typical_home_value is not null
            ) where region_id = ?""", [focus["region_id"]])

    # Zillow publishes no state rents or forecasts: use the median of the
    # state's ZIP codes, clearly labeled
    state_medians = None
    state_geo = next((g for g in geos if g["level"] == "state"), None)
    if state_geo:
        state_medians = one(con, """
            select any_value(state_zip_median_rent) as rent,
                   any_value(state_zip_median_price_to_rent_ratio) as price_to_rent,
                   any_value(state_zip_median_forecast_12m_pct) as forecast_12m,
                   count(typical_rent) as zips_with_rent,
                   count(forecast_12m_pct) as zips_with_forecast
            from marts.zip_comparison_current where state_code = ?""",
            [state_geo["state_code"]])

    # Charts
    since_10y = years_before(as_of, 10)
    value_series, rent_series = [], []
    for g in geos:
        dates, values = trend(con, g["region_id"], "typical_home_value", since_10y)
        value_series.append({"label": g["name"], "short_label": g["short"], "dates": dates,
                             "values": values, "slot": SLOT[g["level"]]})
        dates, values = trend(con, g["region_id"], "typical_rent", date(2015, 1, 1))
        if dates:
            rent_series.append({"label": g["name"], "short_label": g["short"], "dates": dates,
                                "values": values, "slot": SLOT[g["level"]]})

    rates = rows(con, "select * from marts.mortgage_rates_current order by display_order")
    rate_as_of = rates[0]["rate_as_of"]
    rate_series = []
    for slot, (series_id, label, short) in enumerate([
        ("MORTGAGE30US", "30-year fixed", "30-yr"),
        ("MORTGAGE15US", "15-year fixed", "15-yr"),
    ]):
        data = rows(con, """select rate_date, rate_pct from marts.fct_mortgage_rates
                            where series_id = ? and rate_date >= ? order by rate_date""",
                    [series_id, years_before(rate_as_of, 5)])
        rate_series.append({"label": label, "short_label": short, "slot": slot,
                            "dates": [r["rate_date"] for r in data],
                            "values": [r["rate_pct"] for r in data]})

    panel = rows(con, "select * from marts.national_market_panel_current order by display_order")
    for p in panel:
        p["display_value"], p["display_as_of"] = panel_display(p)

    us_afford = next(g for g in geos if g["level"] == "national")["afford"]

    return {
        "focus": focus,
        "geos": geos,
        "rank": rank,
        "state_geo": state_geo,
        "state_medians": state_medians,
        "as_of": as_of,
        "rates": rates,
        "rate_as_of": rate_as_of,
        "panel": panel,
        "us_afford": us_afford,
        "down_payment_pct": us_afford["down_payment_pct"],
        "loan_term_years": us_afford["loan_term_years"],
        "chart_values": line_chart(value_series, "money"),
        "chart_rents": line_chart(rent_series, "money") if rent_series else None,
        "chart_rates": line_chart(rate_series, "percent"),
        "generated": date.today(),
    }


def panel_display(p):
    """Readable value and period for one market panel row."""
    v, units = p["value"], p["units"]
    if units == "Percent":
        value = f"{v:.2f}%"
    elif units == "Listings":
        value = f"{v:,.0f}"
    elif units == "Days":
        value = f"{v:.0f} days"
    elif units == "Months":
        value = f"{v:.1f} months"
    elif units.startswith("Homes"):  # existing home sales, units at annual rate
        value = f"{v / 1_000_000:.2f} million/yr"
    elif "annual rate" in units:     # thousands at an annual rate
        value = f"{v / 1_000:.2f} million/yr"
    else:                            # thousands of units
        value = f"{v:,.0f}k"
    d = p["as_of"]
    period = f"Q{(d.month - 1) // 3 + 1} {d.year}" if p["series_id"] == "DRSFRMACBS" else d.strftime("%b %Y")
    return value, period


# --- Rendering ---------------------------------------------------------------

def find_browser():
    for path in BROWSER_CANDIDATES:
        if path.exists():
            return path
    raise SystemExit("No Microsoft Edge or Google Chrome found; rerun with --html-only.")


def print_to_pdf(html_path, pdf_path, timeout_s=60):
    browser = find_browser()
    # A separate browser profile, so printing works even while the browser is
    # open for normal use. It lives in output/ (git-ignored) and is reused.
    profile = OUTPUT_DIR.parent / ".browser_profile"
    pdf_path.unlink(missing_ok=True)  # so an old PDF can't be mistaken for the new one
    result = subprocess.run(
        [str(browser), "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}",
         html_path.as_uri()],
        capture_output=True, text=True, timeout=120,
    )
    # msedge.exe hands the work to a background process and returns at once,
    # so wait until the PDF exists and its size has stopped changing
    deadline = time.monotonic() + timeout_s
    last_size = -1
    while time.monotonic() < deadline:
        size = pdf_path.stat().st_size if pdf_path.exists() else -1
        if size > 0 and size == last_size:
            return
        last_size = size
        time.sleep(0.5)
    raise SystemExit(f"PDF was not created within {timeout_s} s.\n{result.stderr[-2000:]}")


def main():
    parser = argparse.ArgumentParser(description="Build a housing market report.")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--zip", help="5-digit ZIP code, e.g. 77494")
    which.add_argument("--state", help="2-letter state code, e.g. TX")
    which.add_argument("--us", action="store_true", help="United States")
    parser.add_argument("--html-only", action="store_true", help="skip the PDF")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        context = build_context(con, args)
    finally:
        con.close()

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True,
                      undefined=StrictUndefined)
    env.filters.update({
        "money": fmt_money, "signed_pct": fmt_signed_pct, "signed_pts": fmt_signed_pts,
        "rate": fmt_rate, "num": fmt_num, "month": fmt_month, "day": fmt_day,
    })
    html = env.get_template("report.html.j2").render(**context)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    focus = context["focus"]
    slug = {"zip": f"zip_{focus['short']}", "state": f"state_{focus['short'].lower()}",
            "national": "us"}[focus["level"]]
    html_path = OUTPUT_DIR / f"report_{slug}_{date.today()}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML: {html_path}")

    if not args.html_only:
        pdf_path = html_path.with_suffix(".pdf")
        print_to_pdf(html_path, pdf_path)
        print(f"PDF:  {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()

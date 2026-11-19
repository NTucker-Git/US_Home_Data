# Report Specification

This document defines what the project's housing market report shows, and where each number comes from. It was written before building the data models, so that every source loaded and every table built serves a defined output.

## The report

**"Pick a ZIP, get a report."** One report template that can be generated for any U.S. ZIP code, any state, or the country as a whole. It describes current market conditions, recent trends, and the outlook. The same data will also feed an interactive dashboard.

Requirements:

- **Three geographic levels**: national, state, and ZIP code. Every section is shown at each level where the data exists.
- **Every U.S. ZIP code** that the sources publish, not a hand-picked subset.
- **Real, public data only.** No synthetic or sample data.
- **Free sources only**, with each source's attribution and terms of use respected.
- **Forecasts from two angles**: published forecasts from the data providers, plus a simple projection built in this project, clearly labeled as such.

## Sections

| # | Section | Metrics | Sources | Levels |
|---|---|---|---|---|
| 1 | **Home prices** | Typical home value; 1- and 5-year change; 10-year trend; price per square foot; values at the low and high end of the market | Zillow Home Value Index (all homes, bottom tier, top tier); Redfin; Realtor.com listing prices; S&P Cotality Case-Shiller (national); FHFA House Price Index; Census new home sales prices | US, state, ZIP |
| 2 | **Rents** | Typical rent; 1-year change; HUD Fair Market Rent | Zillow Observed Rent Index; HUD Fair Market Rents and Small Area Fair Market Rents | US, state, ZIP |
| 3 | **Mortgage rates** | Current and historical rates: conventional 30- and 15-year fixed, plus 30-year FHA, VA, USDA, jumbo, and conforming | FRED (Freddie Mac weekly survey; Optimal Blue daily indexes by loan type; 10-year Treasury yield, for the mortgage rate spread) | US |
| 4 | **Affordability** | Monthly payment on a typical home at today's rate, as a share of median household income; price-to-rent ratio; effective property tax rate | Combines Zillow, FRED, and Census American Community Survey; national benchmark of mortgage payments as a share of disposable income | US, state, ZIP |
| 5 | **Market activity** | Homes for sale (active, new, and pending listings); days on market; sale-to-list price ratio; share of listings with price cuts | Redfin; Zillow; Realtor.com | US, state, ZIP |
| 6 | **New supply and construction** | The construction pipeline: permits, permitted but not started, starts, under construction, and completions; new home sales and months' supply | FRED; Census Building Permits Survey | US, state, county |
| 7 | **Outlook** | Published 1-year home value forecast, alongside this project's own projection | Zillow forecasts; project model | US, state, ZIP |
| 8 | **Housing stock** | Number of homes; single-family vs. apartment buildings; when homes were built; home size (square footage, plus rooms and bedrooms); vacancy rates | Census American Community Survey; Realtor.com; Census housing vacancy survey; HUD multifamily property data | US, state, ZIP |
| 9 | **People and income** | Median household income and related demographics | Census American Community Survey | US, state, ZIP |
| 10 | **Neighborhood and access** | School districts and performance; crime; major highways and public transit; distance to airports; grocery stores; utility providers | Census TIGER/Line maps; federal education, crime (FBI), transit, aviation (FAA), food access (USDA), and broadband (FCC) data | Mostly ZIP, via geospatial joins |
| 11 | **Market risk** | Mortgage delinquency trends | Consumer Financial Protection Bureau; Federal Reserve (national) | US, state, county |

## Design notes

- **ZIP codes vs. ZCTAs.** The Census Bureau publishes data by ZIP Code Tabulation Area (ZCTA), an approximation of USPS ZIP codes. A shared geography table with a ZIP-to-ZCTA, county, and metro crosswalk will let every source join on the same keys.
- **Geospatial work.** Section 10 calculates distances and counts from map data (for example, the nearest airport to each ZIP) using DuckDB's spatial extension.
- **Stand-in metrics.** Where the ideal metric has no free national source, the report uses the closest available measure and says so:
  - Home size uses Realtor.com's median listing square footage down to county level, and rooms and bedrooms at ZIP level, since square footage isn't published by ZIP.
  - "Lowest and highest priced homes" uses Zillow's bottom- and top-tier home values (5th-35th and 65th-95th percentiles). Zillow publishes these tiers for states and larger areas but not for ZIP codes, so ZIP reports show the typical (mid-tier) value only.
  - Planned construction uses building permits.
  - Foreclosure history uses mortgage delinquency rates.
- **Considered and excluded.** Lot size, HOA fees, and property ownership history have no free national source. Ownership history also involves private individuals' records, so it is out of scope.
- **Revisions.** Several sources revise past values. Loads use upserts rather than append-only inserts, so the latest published numbers always win.

## Release plan

The report is built in versions, starting with the sources already loaded (FRED and Zillow).

| Version | Contents |
|---|---|
| **v1** | Sections 1 (home prices), 2 (rents), 3 (mortgage rates), and 7 (outlook: Zillow's forecast), plus: **affordability**, the monthly payment (principal and interest, 20% down) on the typical home at today's 30-year rate and the price-to-rent ratio, at every level where the data exists, and payment as a share of median household income nationally; a **national market panel** for sections 5, 6, and 11 (listings, days on market, the construction pipeline, new home sales, months' supply, delinquency); and a **comparison** of each ZIP code with its state and the US, including its rank within the state |
| **v1.1** | This project's own home value projection next to Zillow's forecast, later scored against actual outcomes; inflation-adjusted home values |
| **v2** | State-level FRED series (listings, house price index, unemployment); Census American Community Survey data by ZIP (income, housing stock, property taxes), completing sections 8 and 9; the **full monthly payment** (v1's principal and interest plus property tax and homeowners insurance) and payment as a share of income by state and ZIP, completing affordability; a reference table of every FRED series with its units, owner, and terms |

## Build status

| Section | Status |
|---|---|
| 1, 2. Home prices, rents | Zillow home values and rents loaded and modeled in dbt for the US, states, metros, and ZIP codes; first marts built. Price per square foot and HUD Fair Market Rents to come |
| 3. Mortgage rates | Marts built: every rate by date, and the latest rates with 1-week and 1-year changes, 52-week range, and spread over the 10-year Treasury |
| 7. Outlook | Marts built: Zillow's 1-, 3-, and 12-month forecasts for the US, metros, and ZIP codes, also in dollars; each release kept for later scoring against actual outcomes. This project's own projection comes in v1.1 |
| 4. Affordability | Mart built for the US, states, metros, and ZIP codes: monthly principal-and-interest payment on the typical home (30-year fixed, 20% down) now and a year earlier, price-to-rent ratio, and national payment-to-income. Property tax, insurance, and local income come in v2 |
| 5, 6, 11. Market activity, new supply, market risk | National panel built: listings, share of listings with a price cut, days on market, existing and new home sales, the construction pipeline, months' supply, and delinquency, each with its 1-year change. State and ZIP sources next |
| 8. Housing stock | National series loaded (FRED); Census data in v2 |
| 9, 10. People and income, neighborhood | Planned (national income indicators loaded) |
| ZIP comparison | Mart built: every ZIP next to its state and the US (home value, changes, payment, rent, price-to-rent, forecast), with its rank and percentile within the state. Where Zillow has no state figure (rent, forecast), the state comparison is the median across the state's ZIP codes |

## Attribution

- Data from FRED, Federal Reserve Bank of St. Louis.
- Data Provided by Zillow Group.

Additional source attributions will be added as each source is loaded.

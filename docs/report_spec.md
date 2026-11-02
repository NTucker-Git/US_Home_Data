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
| 1 | **Home prices** | Typical home value; 1- and 5-year change; 10-year trend; price per square foot; values at the low and high end of the market | Zillow Home Value Index (all homes, bottom tier, top tier); Redfin; S&P Cotality Case-Shiller (national); FHFA House Price Index | US, state, ZIP |
| 2 | **Rents** | Typical rent; 1-year change; HUD Fair Market Rent | Zillow Observed Rent Index; HUD Fair Market Rents and Small Area Fair Market Rents | US, state, ZIP |
| 3 | **Mortgage rates** | Current and historical rates: conventional 30- and 15-year fixed, plus 30-year FHA, VA, USDA, jumbo, and conforming | FRED (Freddie Mac weekly survey; Optimal Blue daily indexes by loan type) | US |
| 4 | **Affordability** | Monthly payment on a typical home at today's rate, as a share of median household income; price-to-rent ratio; effective property tax rate | Combines Zillow, FRED, and Census American Community Survey | US, state, ZIP |
| 5 | **Market activity** | Homes for sale; days on market; sale-to-list price ratio; share of listings with price cuts | Redfin; Zillow | US, state, ZIP |
| 6 | **New supply and construction** | Housing starts; building permits | FRED; Census Building Permits Survey | US, state, county |
| 7 | **Outlook** | Published 1-year home value forecast, alongside this project's own projection | Zillow forecasts; project model | US, state, ZIP |
| 8 | **Housing stock** | Number of homes; single-family vs. apartment buildings; when homes were built; rooms and bedrooms | Census American Community Survey; HUD multifamily property data | US, state, ZIP |
| 9 | **People and income** | Median household income and related demographics | Census American Community Survey | US, state, ZIP |
| 10 | **Neighborhood and access** | School districts and performance; crime; major highways and public transit; distance to airports; grocery stores; utility providers | Census TIGER/Line maps; federal education, crime (FBI), transit, aviation (FAA), food access (USDA), and broadband (FCC) data | Mostly ZIP, via geospatial joins |
| 11 | **Market risk** | Mortgage delinquency trends | Consumer Financial Protection Bureau | US, state, county |

## Design notes

- **ZIP codes vs. ZCTAs.** The Census Bureau publishes data by ZIP Code Tabulation Area (ZCTA), an approximation of USPS ZIP codes. A shared geography table with a ZIP-to-ZCTA, county, and metro crosswalk will let every source join on the same keys.
- **Geospatial work.** Section 10 calculates distances and counts from map data (for example, the nearest airport to each ZIP) using DuckDB's spatial extension.
- **Stand-in metrics.** Where the ideal metric has no free national source, the report uses the closest available measure and says so:
  - Home size uses rooms and bedrooms, since square footage isn't published by ZIP.
  - "Lowest and highest priced homes" uses Zillow's bottom- and top-tier home values.
  - Planned construction uses building permits.
  - Foreclosure history uses mortgage delinquency rates.
- **Considered and excluded.** Lot size, HOA fees, and property ownership history have no free national source. Ownership history also involves private individuals' records, so it is out of scope.
- **Revisions.** Several sources revise past values. Loads use upserts rather than append-only inserts, so the latest published numbers always win.

## Build status

| Section | Status |
|---|---|
| 3. Mortgage rates | Data loaded (FRED) |
| 1, 6. Home prices, new supply | National series loaded (FRED); ZIP and state sources next |
| All others | Planned |

## Attribution

Data from FRED, Federal Reserve Bank of St. Louis. Additional source attributions will be added as each source is loaded.

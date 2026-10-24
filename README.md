# nem-sa-analysis

![CI](https://github.com/mochiquin/nem-sa-analysis/actions/workflows/ci.yml/badge.svg)

An end-to-end data project on South Australia's wholesale electricity market,
built on public AEMO data: ingest raw market files, clean them, load them into
PostgreSQL, and answer concrete questions with SQL.

**Questions this project sets out to answer**

1. When, and how often, does the SA spot price go negative, and how does that
   relate to wind and solar output?
2. What could a battery have earned by charging in low-price intervals and
   discharging in high-price ones?

> Status: pipeline scaffold. Analysis and dashboard are in progress.

## Architecture

```
NEMweb "Current" (5-min zipped CSVs) ──► own parser ─┐
                                                      ├─► clean ─► PostgreSQL ─► SQL analysis ─► dashboard
MMSDM monthly archives ─────────────► NEMOSIS ───────┘
```

| Path | What it does |
| --- | --- |
| `src/nemsa/nemweb/parse.py` | Parses AEMO's multi-table "C/I/D" CSV format, where one file holds several tables |
| `src/nemsa/nemweb/clean.py` | Typing, de-duplication by latest revision, gap detection |
| `src/nemsa/nemweb/fetch.py` | Lists and downloads new files from NEMweb, with caching and retries |
| `src/nemsa/backfill.py` | Bulk history via [NEMOSIS](https://github.com/UNSW-CEEM/NEMOSIS) |
| `src/nemsa/ingest.py` | Idempotent incremental load, one transaction per file |
| `db/schema.sql` | Tables, ingest log, and the `v_price` analysis view |
| `sql/analysis/` | Analysis queries |

## Data handling decisions

- **Timestamps** are AEMO market time (AEST, UTC+10, no daylight saving).
  `SETTLEMENTDATE` is the *end* of a 5-minute interval; `interval_start` is
  derived in the schema.
- **Negative prices and price-cap events are kept.** They are real market
  outcomes, not data errors, so no statistical outlier removal is applied.
- **Interventions:** when AEMO intervenes, two dispatch runs are published.
  Both are stored; `v_price` uses the non-intervention run (`INTERVENTION = 0`),
  which sets the market price.
- **Revisions:** if a row appears more than once, the latest `LASTCHANGED` wins.
- **Gaps are reported, not silently filled** (`nemsa gaps`).

## Quick start

### With Docker only

```bash
cp .env.example .env
docker compose up -d db                                   # PostgreSQL 16, schema applied on first start
docker compose --profile cli build                        # build the pipeline image

docker compose run --rm nemsa -v backfill --start 2025-10-01 --end 2025-11-01
docker compose run --rm nemsa -v ingest --limit 12
docker compose run --rm nemsa gaps

docker compose exec -T db psql -U nemsa -d nemsa < sql/analysis/01_negative_prices.sql
```

Downloaded raw files are cached in `./data` on the host.

### With a local Python environment

```bash
cp .env.example .env
docker compose up -d db
pip install -e ".[dev]"

nemsa -v backfill --start 2025-10-01 --end 2025-11-01   # one month of history
nemsa -v ingest --limit 12                              # newest hour from NEMweb
nemsa gaps

psql postgresql://nemsa:nemsa@localhost:5432/nemsa -f sql/analysis/01_negative_prices.sql
```

Run the tests with `pytest`. Database tests run when Postgres is reachable
(locally via Docker, and in CI).

## Roadmap

- [x] Parser, cleaning rules, Postgres schema, CI
- [ ] Load 1–2 years of SA history and validate against AEMO's published figures
- [ ] Generation by fuel type (unit SCADA + generator registration data)
- [ ] Negative-price analysis
- [ ] Battery arbitrage simulation
- [ ] Dashboard and deployment

## Data source and licence

Market data © AEMO, used under the
[AEMO Copyright Permissions Notice](https://aemo.com.au/privacy-and-legal-notices/copyright-permissions)
with attribution to AEMO as its author. Historical data is retrieved with
NEMOSIS (UNSW Collaboration on Energy and Environmental Markets).

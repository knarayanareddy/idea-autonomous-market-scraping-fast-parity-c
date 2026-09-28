# Autonomous Market Scraping & Fast Parity Check

> High-speed secondary marketplace crawler (eBay & Marktplaats) utilizing embedded DuckDB local parity checks to eliminate redundant downstream Apify cloud scraping runs and save 80%+ on data ingestion costs.

[![CI Status](https://img.shields.io/badge/tests-6%20passed-brightgreen.svg)]()
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1+-yellow.svg)](https://duckdb.org)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)]()

---

## 🚀 Overview

When monitoring secondary marketplaces for newly posted deals or price drops, executing full-browser cloud scrapers (e.g. Apify actors, ScrapingBee, or Playwright farms) on every scheduled interval costs money and API credits—even when 99% of search results are identical to the previous crawl.

**Market Parity Engine** implements an intelligent two-tier architecture:
1. **Tier 1 (Fast Crawl):** Lightweight, low-overhead index scraper fetches search cards.
2. **Tier 2 (DuckDB Parity Engine):** Compares listings against local embedded DuckDB analytical state using cryptographic content hashing (`external_id + title + price + currency`).
3. **Actionable Delta Gating:**
   - **In Parity:** 0 new items & 0 price drops $\rightarrow$ cloud scraper execution is **bypassed** entirely.
   - **Disparity Detected:** New items or price drops $\rightarrow$ triggers targeted Apify actors only for the affected URLs.

---

## 🛠 Installation & Setup

```bash
# Clone the repository
git clone https://github.com/knarayanareddy/idea-autonomous-market-scraping-fast-parity-c.git
cd idea-autonomous-market-scraping-fast-parity-c

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 💻 Usage & CLI Commands

### 1. Run Pipeline (Crawl -> Parity Check -> Trigger -> Commit)
```bash
# Run against mock simulation (ideal for offline tests and benchmarks)
python main.py run --source mock --query "thinkpad x1"

# Run against live eBay search index
python main.py run --source ebay --query "macbook pro m3"

# Preview only without writing to DuckDB
python main.py run --source mock --query "rtx 4090" --dry-run
```

### 2. View Cost Savings & Analytical Metrics
```bash
python main.py stats
```
Output:
```text
DuckDB Market Parity Metrics & Cost Savings
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric                          ┃ Value ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Tracked Listings          │ 42    │
│ Total Parity Runs               │ 15    │
│ Cloud Deep Scrapes Triggered    │ 3     │
│ Cloud Scrapes Avoided (Savings) │ 12    │
│ Cloud Cost Efficiency           │ 80.0% │
└─────────────────────────────────┴───────┘
```

---

## 🧪 Running the Test Suite

```bash
pytest -v
```

All 6 test cases verify:
- Deterministic cryptographic hashing across casing and whitespace variations
- DuckDB transactional upserts and price history tracking
- Delta detection for first-time crawls vs. steady-state parity
- Price drop triggers and threshold evaluation

---

## 📄 License
MIT License.

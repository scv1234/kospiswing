# Implementation Plan: Stock Analysis Dashboard App

## Goal
Create a Streamlit-based dashboard application for daily stock market analysis, swing trading screening, and trade journaling.

## User Review Required
None. This is a straightforward implementation of the user's request.

## Proposed Changes

### Directory Structure
```
c:\Users\User\Desktop\app\stockanalysis\
├── app.py                  # Main entry point
├── pages/
│   ├── 1_Daily_Top_Down.py # Top-Down Report Page
│   ├── 2_Swing_Trading.py  # Swing Trading Report Page
│   └── 3_Trading_Journal.py# Trading Journal Page
├── utils/
│   ├── __init__.py
│   ├── data_fetcher.py     # Data fetching logic (pykrx)
│   └── analysis.py         # Screening logic (refactored swing_screener.py)
├── data/
│   └── trade_journal.csv   # Trade records storage
├── requirements.txt
└── task_list.md
```

### 1. Backend Logic (Utils)
#### [NEW] `utils/data_fetcher.py`
- Functions to fetch KOSPI/KOSDAQ indices, foreign/institution net buying by sector using `pykrx`.
- Function to fetch OHLCV and fundamental data for analysis.

#### [NEW] `utils/analysis.py`
- Refactor existing `swing_screener.py` logic into a function `run_swing_analysis()`.
- Instead of printing to stdout, it will return:
    - `df_all`: DataFrame of all screened stocks.
    - `top_picks`: List of dictionaries for TOP 3 stocks.

### 2. Frontend (Streamlit)
#### [NEW] `app.py`
- Sidebar with navigation and an "Update Data" button.
- Main page showing a welcome message or summary.

#### [NEW] `pages/1_Daily_Top_Down.py`
- Metric cards for Market Indices (KOSPI, USD/KRW - manual input or estimated).
- Charts for Sector Performance (Net Buying).
- Text area for "Macro Analysis" notes (optional user input).

#### [NEW] `pages/2_Swing_Trading.py`
- Button to run analysis.
- Display TOP 3 stocks with detailed metrics (Target Price, Stop Loss).
- Display full table of screened stocks.

#### [NEW] `pages/3_Trading_Journal.py`
- `st.data_editor` to add/edit trades.
- Save mechanism to `data/trade_journal.csv`.

## Verification Plan
### Automated Tests
- None planned for this rapid prototype.

### Manual Verification
1. **Run App**: Execute `streamlit run app.py`.
2. **Top-Down Page**: Verify KOSPI index and sector data loads correctly.
3. **Swing Page**: Click "Run Analysis", verify that it returns the same stocks as the CLI script (e.g., SK Securities, Korea Asset Trust).
4. **Journal Page**: Add a test trade, save, reload page to verify persistence.

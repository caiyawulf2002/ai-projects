# Shared Financial Data Schema
*Canonical Pydantic models used across P3, P4, and P5.*
*If you need a new field, add it here first, then use it everywhere.*
*Never invent field names inline — check here first.*

---

## Why this file exists

P3 (analyzer), P5 (comps agent), and P4 (optimizer) all handle financial data.
Without a shared schema, each project will name fields differently:
- P3 calls it `gross_margin`, P5 calls it `gross_margin_pct`, P4 expects `gm`
- None of them can talk to each other

This file defines the single source of truth. All three projects import from
`src/models/financial.py` which mirrors these definitions exactly.

---

## Core models

### CompanyIdentifier
```python
class CompanyIdentifier(BaseModel):
    ticker: str                    # e.g. "AAPL"
    company_name: str              # e.g. "Apple Inc."
    cik: str                       # SEC EDGAR CIK number
    sector: str                    # e.g. "Technology"
    industry: str                  # e.g. "Consumer Electronics"
    filing_year: int               # fiscal year of the data
```

### IncomeStatement
```python
class IncomeStatement(BaseModel):
    revenue: float                 # total revenue ($M)
    gross_profit: float            # revenue - COGS ($M)
    operating_income: float        # EBIT ($M)
    net_income: float              # bottom line ($M)
    ebitda: float | None = None    # if available
    rd_expense: float | None = None
    sga_expense: float | None = None

    # Derived margins (calculated, not extracted)
    gross_margin: float | None = None      # gross_profit / revenue
    operating_margin: float | None = None  # operating_income / revenue
    net_margin: float | None = None        # net_income / revenue
```

### BalanceSheet
```python
class BalanceSheet(BaseModel):
    total_assets: float
    total_liabilities: float
    total_equity: float
    cash_and_equivalents: float
    total_debt: float              # short + long term
    current_assets: float
    current_liabilities: float

    # Derived ratios
    current_ratio: float | None = None     # current_assets / current_liabilities
    debt_to_equity: float | None = None    # total_debt / total_equity
```

### CashFlowStatement
```python
class CashFlowStatement(BaseModel):
    operating_cash_flow: float
    capex: float                   # capital expenditures (negative = outflow)
    free_cash_flow: float          # operating_cash_flow + capex

    # Derived
    fcf_conversion: float | None = None    # free_cash_flow / net_income
```

### FinancialRatios (the 12 from the plan)
```python
class FinancialRatios(BaseModel):
    # Profitability
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    roe: float | None = None               # net_income / total_equity
    roa: float | None = None               # net_income / total_assets

    # Leverage & liquidity
    current_ratio: float | None = None
    debt_to_equity: float | None = None
    interest_coverage: float | None = None # ebit / interest_expense

    # Valuation
    pe_ratio: float | None = None
    ev_to_ebitda: float | None = None
    price_to_fcf: float | None = None

    # Growth
    revenue_growth_yoy: float | None = None

    # Anomaly flags (set by XGBoost classifier in P3)
    margin_compression_flag: bool = False
    rising_leverage_flag: bool = False
    fcf_divergence_flag: bool = False
    earnings_surprise_prediction: str | None = None  # "beat" | "miss" | None
    earnings_surprise_probability: float | None = None
```

### CompanyFinancials (top-level container)
```python
class CompanyFinancials(BaseModel):
    identifier: CompanyIdentifier
    income_statement: IncomeStatement
    balance_sheet: BalanceSheet
    cash_flow: CashFlowStatement
    ratios: FinancialRatios
    source_filing: str             # e.g. "10-K 2023" or "10-Q Q3 2024"
    extracted_at: str              # ISO timestamp
    extraction_confidence: float   # 0.0–1.0, set by P3's RAG pipeline
```

### CompsTable (P5 output, P4 input)
```python
class CompsTable(BaseModel):
    target_company: CompanyIdentifier
    peers: list[CompanyFinancials]
    median_ev_to_ebitda: float | None = None
    median_pe: float | None = None
    median_ev_to_revenue: float | None = None
    valuation_premium_discount: float | None = None  # vs peer median
    narrative: str | None = None   # LLM-generated summary
    generated_at: str              # ISO timestamp
```

### OptimizerInput (P4 input — consumes P3 + P5 outputs)
```python
class AssetSignals(BaseModel):
    ticker: str
    expected_return: float         # annualized, from LSTM or historical mean
    quality_score: float | None = None   # from P3 — 0.0 to 1.0
    anomaly_flags: list[str] = []  # from P3 XGBoost flags
    peer_valuation_premium: float | None = None  # from P5

class OptimizerInput(BaseModel):
    assets: list[AssetSignals]
    lookback_days: int = 252       # for covariance calculation
    target_return: float | None = None
    max_position_size: float = 0.4
    min_position_size: float = 0.0
    sector_constraints: dict[str, float] = {}  # sector → max weight
```

---

## Shared utility functions

These live in `src/utils/financial_utils.py` (create once, import everywhere):

```python
def calculate_ratios(income: IncomeStatement,
                     balance: BalanceSheet,
                     cashflow: CashFlowStatement,
                     market_cap: float | None = None) -> FinancialRatios:
    """Calculate all 12 ratios from the three statement inputs."""
    ...

def normalize_filing_currency(value: float, unit: str) -> float:
    """Convert 'thousands', 'millions', 'billions' to consistent $M."""
    ...

def validate_financial_data(company: CompanyFinancials) -> list[str]:
    """Return list of data quality issues (empty list = clean)."""
    ...
```

---

## Version history

| Date | Change | Who |
|------|--------|-----|
| [DATE] | Initial schema defined | Caiya |

*When you add or change a model, add a row here.*

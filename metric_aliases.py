"""Reusable US-GAAP tag aliases, ordered from preferred to fallback tags."""

METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "Revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "Revenues",
    ),
    "Net Income": (
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ),
    "EBIT": (
        "OperatingIncomeLoss",
        "IncomeLossFromContinuingOperationsBeforeInterestExpenseInterestIncomeIncomeTaxesExtraordinaryItemsNoncontrollingInterestsNet",
    ),
    "EBT": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
    ),
    "Interest Expense": (
        "InterestExpenseNonoperating",
        "InterestAndDebtExpense",
        "InterestExpense",
        "InterestExpenseNet",
        "InterestIncomeExpenseNonoperatingNet",
    ),
    "Interest Income": (
        "InterestIncome",
        "InvestmentIncomeInterest",
        "InterestAndDividendIncome",
    ),
    "Cash": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "Cash",
    ),
    "Investments": (
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesCurrent",
        "DebtSecuritiesAvailableForSaleCurrent",
    ),
    "Debt": (
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtCurrent",
        "ShortTermBorrowings",
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebt",
    ),
    "Preferred Equity": (
        "PreferredStockValue",
        "PreferredStockCarryingValue",
        "TemporaryEquityCarryingAmountAttributableToParent",
        "PreferredStocksIncludingAdditionalPaidInCapital",
    ),
    # Finance-lease liabilities are usually rolled into broader balance-sheet
    # captions (Other current/long-term liabilities, or Short-/Long-term debt)
    # and only segregated in the Leases note. XBRL exposes that segregated
    # note-level amount directly, so these tags give the finance-lease
    # component without pulling the whole parent caption. When a filer treats
    # finance leases as immaterial the tag is simply absent, and the extractor
    # records 0.0 with no tag/date rather than an assumed value.
    "Finance Lease Short-Term": (
        "FinanceLeaseLiabilityCurrent",
        "CapitalLeaseObligationsCurrent",
    ),
    "Finance Lease Long-Term": (
        "FinanceLeaseLiabilityNoncurrent",
        "CapitalLeaseObligationsNoncurrent",
    ),
    "D&A": (
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
        "AmortizationOfIntangibleAssets",
    ),
    "Impairment": (
        "AssetImpairmentCharges",
        "GoodwillImpairmentLoss",
        "ImpairmentOfIntangibleAssetsExcludingGoodwill",
        "RestructuringAndImpairmentCharges",
        "PropertyPlantAndEquipmentImpairment",
    ),
}


LTM_METRICS = (
    "Revenue",
    "Net Income",
    "EBIT",
    "EBT",
    "Interest Expense",
    "Interest Income",
    "D&A",
    "Impairment",
)

BALANCE_SHEET_METRICS = (
    "Cash",
    "Investments",
    "Debt",
    "Preferred Equity",
    "Finance Lease Short-Term",
    "Finance Lease Long-Term",
)


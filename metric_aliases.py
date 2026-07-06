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

BALANCE_SHEET_METRICS = ("Cash", "Investments", "Debt", "Preferred Equity")


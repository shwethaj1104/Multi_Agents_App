import csv
import io
import json
from decimal import Decimal

from loandesk.domain.contracts import ApplicationInput

SAMPLES = [
    {
        "key": "complete",
        "business_name": "Cedar & Grain Bakery",
        "industry": "Food & beverage",
        "amount": "150000",
        "operating_months": 48,
        "revenue": "900000",
        "expenses": "650000",
        "debt": "30000",
        "bank_income": "900000",
        "description": "Complete documents and consistent figures.",
    },
    {
        "key": "missing",
        "business_name": "Harbor Supply Co.",
        "industry": "Wholesale trade",
        "amount": "280000",
        "operating_months": 36,
        "revenue": "1200000",
        "expenses": "850000",
        "debt": "50000",
        "bank_income": None,
        "description": "Bank transaction records are missing.",
    },
    {
        "key": "mismatch",
        "business_name": "Northline Studio",
        "industry": "Professional services",
        "amount": "85000",
        "operating_months": 30,
        "revenue": "600000",
        "expenses": "400000",
        "debt": "10000",
        "bank_income": "420000",
        "description": "Statement revenue differs from bank income.",
    },
    {
        "key": "policy",
        "business_name": "Juniper Workshop",
        "industry": "Manufacturing",
        "amount": "150000",
        "operating_months": 12,
        "revenue": "240000",
        "expenses": "225000",
        "debt": "12000",
        "bank_income": "240000",
        "description": "Operating history, revenue and repayment policy exceptions.",
    },
    {
        "key": "insufficient",
        "business_name": "Dune Services",
        "industry": "Business services",
        "amount": "50000",
        "operating_months": 36,
        "revenue": None,
        "expenses": None,
        "debt": None,
        "bank_income": None,
        "description": "No evidence has been supplied.",
    },
]


# Produce exactly twelve monthly income rows for a fictional case; real transaction data is never
# used.
def sample_bank_csv(total: str) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "amount", "category", "description"])
    monthly = Decimal(total) / 12
    for month in range(1, 13):
        writer.writerow([f"2025-{month:02d}-15", str(monthly), "income", "Synthetic monthly sales"])
    return output.getvalue().encode()


# Return input fields and optional synthetic evidence files for the requested sample template.
def build_sample_case(key: str) -> tuple[ApplicationInput, list[tuple[str, str, bytes]]]:
    sample = next((item for item in SAMPLES if item["key"] == key), None)
    if sample is None:
        raise ValueError("Unknown sample case.")
    application = ApplicationInput(
        business_name=sample["business_name"],
        industry=sample["industry"],
        amount=sample["amount"],
        operating_months=sample["operating_months"],
        purpose="Purchase equipment for business expansion.",
    )
    files = []
    if sample["revenue"] is not None:
        statement = {
            "annual_revenue": sample["revenue"],
            "annual_expenses": sample["expenses"],
            "annual_debt_service": sample["debt"],
            "period": "2025",
            "currency": "AED",
            "synthetic": True,
        }
        files.append(
            ("profit-and-loss.json", "profit_and_loss", json.dumps(statement, indent=2).encode())
        )
    if sample["bank_income"] is not None:
        files.append(
            ("bank-transactions.csv", "bank_transactions", sample_bank_csv(sample["bank_income"]))
        )
    return application, files

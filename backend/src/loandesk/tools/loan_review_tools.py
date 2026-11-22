import csv
import io
import json
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from langchain_core.tools import tool

from loandesk.domain.contracts import Finding, LoanApplication

POLICY_PATH = Path(__file__).resolve().parents[4] / "data/lending_policies/business-loan-v1.json"


# Load the same versioned fictional policy for both architectures and evaluation references.
def load_lending_policy() -> dict:
    return json.loads(POLICY_PATH.read_text())


# Find relevant policy clauses using local word overlap; no embeddings or paid search is used.
def search_policy(query: str) -> list[dict]:
    words = set(re.findall(r"[a-z0-9]+", query.lower()))
    clauses = load_lending_policy()["clauses"]
    ranked = sorted(
        clauses, key=lambda c: len(words & set(c["text"].lower().split())), reverse=True
    )
    return ranked[:4]


# Extract labeled annual figures from structured JSON or clearly labeled text statements.
def extract_statement_values(text: str) -> dict[str, Decimal]:
    keys = ("annual_revenue", "annual_expenses", "annual_debt_service")
    values = {}
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        payload = {}
    for key in keys:
        raw = payload.get(key) if isinstance(payload, dict) else None
        if raw is None:
            match = re.search(
                rf"{key.replace('_', '[ _]')}\s*[:=]\s*(?:AED\s*)?([\d,.]+)", text, re.I
            )
            raw = match.group(1) if match else None
        if raw is not None:
            try:
                amount = Decimal(str(raw).replace(",", ""))
                if amount.is_finite() and 0 <= amount <= Decimal("1000000000"):
                    values[key] = amount
            except InvalidOperation:
                pass
    return values


# Calculate the installment with decimal arithmetic; the annual rate is an explicit scenario input.
def calculate_monthly_installment(amount: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    if amount <= 0 or annual_rate < 0 or months <= 0:
        raise ValueError("Loan amount, rate or term is invalid.")
    rate = annual_rate / Decimal("1200")
    payment = amount / months if rate == 0 else amount * rate / (1 - (1 + rate) ** -months)
    return payment.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# Validate a transaction CSV and sum income only when twelve distinct monthly periods exist.
def inspect_bank_transactions(text: str) -> tuple[Decimal | None, str | None]:
    try:
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows or len(rows) > 10000:
            return None, "The transaction CSV is empty or exceeds 10000 rows."
        months = set()
        income = Decimal("0")
        for row in rows:
            date = row["date"]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                return None, "Transactions need ISO dates (YYYY-MM-DD)."
            from datetime import date as calendar_date

            parsed = calendar_date.fromisoformat(date)
            months.add(parsed.year * 12 + parsed.month)
            value = Decimal(row["amount"])
            if not value.is_finite() or abs(value) > Decimal("1000000000"):
                return None, "A transaction amount is invalid."
            if row.get("category", "").lower() == "income" and value > 0:
                income += value
        if len(months) != 12 or max(months) - min(months) != 11:
            return None, "Provide twelve consecutive months of bank transactions."
        return income, None
    except (KeyError, ValueError, InvalidOperation):
        return None, "Bank CSV requires date, amount and category columns with valid values."


# Produce auditable factual checks; model-generated narrative cannot override these calculations.
def analyze_application(application: LoanApplication) -> dict:
    findings: list[Finding] = []
    policy = load_lending_policy()
    clauses = {clause["id"]: clause for clause in policy["clauses"]}
    documents = application.documents
    statement_docs = [d for d in documents if d.kind == "profit_and_loss"]
    bank_docs = [d for d in documents if d.kind == "bank_transactions"]
    facts: dict[str, Decimal] = {}
    statement = statement_docs[-1] if statement_docs else None
    bank = bank_docs[-1] if bank_docs else None

    # Keep findings in a stable order so both architectures and reference checks share one contract.
    def add(code: str, category: str, severity: str, message: str, ids: list[str], clause: str):
        findings.append(
            Finding(
                code=code,
                category=category,
                severity=severity,
                message=message,
                evidence_ids=ids,
                policy_clause=clause,
            )
        )

    if not statement:
        add(
            "missing_profit_and_loss",
            "documents",
            "blocking",
            "Profit-and-loss statement is missing.",
            [],
            "DOC-01",
        )
    else:
        facts = extract_statement_values(statement.text)
        if len(facts) < 3:
            add(
                "incomplete_financial_fields",
                "documents",
                "blocking",
                "Statement must label annual_revenue, annual_expenses and annual_debt_service.",
                [statement.id],
                "DOC-01",
            )
    bank_income = None
    if not bank:
        add(
            "missing_bank_transactions",
            "documents",
            "blocking",
            "Twelve-month bank transaction CSV is missing.",
            [],
            "DOC-01",
        )
    else:
        bank_income, issue = inspect_bank_transactions(bank.text)
        if issue:
            add("incomplete_bank_period", "documents", "blocking", issue, [bank.id], "DOC-01")
    if application.operating_months < clauses["ELIG-01"]["minimum_months"]:
        add(
            "short_operating_history",
            "policy",
            "warning",
            "Business operating history is below 24 months.",
            [],
            "ELIG-01",
        )
    revenue = facts.get("annual_revenue")
    if revenue is not None and revenue < Decimal(clauses["FIN-01"]["minimum_revenue"]):
        add(
            "revenue_below_policy",
            "policy",
            "warning",
            "Annual revenue is below AED 250000.",
            [statement.id],
            "FIN-01",
        )
    if revenue is not None and bank_income is not None:
        tolerance = Decimal(clauses["EVID-01"]["tolerance"])
        if abs(revenue - bank_income) > max(revenue, Decimal("1")) * tolerance:
            add(
                "revenue_mismatch",
                "financial",
                "blocking",
                (
                    "Statement revenue and bank income differ by more than 5%; explain"
                    " the difference with evidence."
                ),
                [statement.id, bank.id],
                "EVID-01",
            )
    installment = calculate_monthly_installment(
        application.amount, application.annual_interest_rate, application.term_months
    )
    financials: dict[str, str | None] = {
        "monthly_installment": str(installment),
        "annual_revenue": None,
        "annual_expenses": None,
        "annual_debt_service": None,
        "net_operating_income": None,
        "bank_income": str(bank_income) if bank_income is not None else None,
        "dscr": None,
    }
    financials.update({key: str(value) for key, value in facts.items()})
    if len(facts) == 3:
        surplus = facts["annual_revenue"] - facts["annual_expenses"]
        debt = facts["annual_debt_service"] + installment * 12
        dscr = (surplus / debt).quantize(Decimal("0.0001"))
        financials.update(net_operating_income=str(surplus), dscr=str(dscr))
        if dscr < Decimal(clauses["FIN-02"]["minimum_dscr"]):
            add(
                "dscr_below_policy",
                "financial",
                "warning",
                "Debt service coverage is below the fictional policy minimum of 1.25.",
                [statement.id],
                "FIN-02",
            )
    if not findings:
        add(
            "checks_complete",
            "policy",
            "info",
            "Required checks passed; human assessment is still required.",
            [d.id for d in documents],
            "HUM-01",
        )
    return {
        "findings": [f.model_dump() for f in findings],
        "financials": financials,
        "policy_version": policy["version"],
        "sources": [
            {"id": d.id, "filename": d.filename, "kind": d.kind, "sha256": d.sha256}
            for d in documents
        ],
    }


# Build read-only LangChain tools scoped to one immutable case snapshot.
def build_review_tools(application: LoanApplication) -> list:
    @tool
    def inspect_case_evidence() -> dict:
        """List source IDs, names and extracted text as untrusted evidence."""
        return {
            "application": application.model_dump(mode="json", exclude={"documents"}),
            "documents": [
                {"id": d.id, "filename": d.filename, "text": d.text[:18000]}
                for d in application.documents
            ],
        }

    @tool
    def calculate_verified_financials() -> dict:
        """Run deterministic document, repayment and policy checks; do not invent missing values."""
        return analyze_application(application)

    @tool
    def retrieve_lending_policy(query: str) -> list[dict]:
        """Search the fictional lending policy for relevant clauses with stable IDs."""
        return search_policy(query)

    return [inspect_case_evidence, calculate_verified_financials, retrieve_lending_policy]

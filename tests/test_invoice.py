"""Phase 4 — GST invoice: golden reproduction, gapless numbering, immutability,
credit notes.

Quotes are crafted directly (an issued quote grossing ₹1,69,700) so the invoice's
tax split can be checked against the golden fixture REPL/2627/TP10 without rebuilding
a whole itinerary — the pricing math itself is covered by test_golden_invoice_tp10.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from app.api.deps import current_org_id
from app.db import get_session
from app.main import app
from app.models import Itinerary, Organization, Project, Quote
from app.models.enums import GstTreatment
from app.services import invoice as inv
from app.services.invoice import fiscal_year
from app.services.invoice_pdf import amount_in_words, render_invoice_pdf, rupees
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

_INVOICE_DAY = date(2026, 8, 2)


def _org(session: Session) -> Organization:
    org = Organization(name="Rootsvida QA", slug=f"inv-{uuid.uuid4().hex[:8]}",
                       gstin="05AANCR1978G1Z1", pan="AANCR1978G",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    session.add(org)
    session.flush()
    return org


def _issued_quote(session: Session, org: Organization, *, gross: str = "169700",
                  status: str = "issued",
                  treatment: GstTreatment = GstTreatment.CGST_SGST) -> Quote:
    project = Project(org_id=org.id, code=f"TP-{uuid.uuid4().hex[:6]}",
                      client_name="Golden Client", client_country="IN")
    session.add(project)
    session.flush()
    it = Itinerary(org_id=org.id, project_id=project.id, title="Golden Triangle",
                   start_date=date(2026, 7, 18), end_date=date(2026, 7, 23))
    session.add(it)
    session.flush()
    q = Quote(org_id=org.id, project_id=project.id, itinerary_id=it.id, version=1,
              status=status, gst_rate=Decimal("5.00"), gst_treatment=treatment,
              rounding_policy="gross_nearest_100", total_gross=Decimal(gross),
              pricing_snapshot={"inputs": {"tax_rule": {"hsn": "998555"}}},
              engine_version="test")
    session.add(q)
    session.flush()
    return q


def test_golden_invoice_reproduced(db_session: Session) -> None:
    org = _org(db_session)
    q = _issued_quote(db_session, org)
    invoice = inv.generate_invoice(db_session, org.id, q.id, invoice_date=_INVOICE_DAY)

    assert invoice.number == f"RV/{fiscal_year(_INVOICE_DAY)}/0001"
    assert invoice.taxable == Decimal("161619.05")
    assert invoice.cgst == Decimal("4040.48")
    assert invoice.sgst == Decimal("4040.48")
    assert invoice.igst == Decimal("0.00")
    assert invoice.rounding_adjustment == Decimal("-0.01")
    assert invoice.total == Decimal("169700.00")
    # The reconcile invariant (also a DB CHECK).
    assert (invoice.taxable + invoice.cgst + invoice.sgst + invoice.igst
            + invoice.rounding_adjustment == invoice.total)
    assert invoice.hsn == "998555"
    assert invoice.gst_treatment is GstTreatment.CGST_SGST
    assert invoice.seller_gstin == "05AANCR1978G1Z1"
    assert invoice.buyer_name == "Golden Client"
    assert invoice.place_of_supply == "Uttarakhand"
    assert len(invoice.lines) == 1
    assert invoice.lines[0].taxable_value == Decimal("161619.05")


def test_numbers_are_gapless(db_session: Session) -> None:
    org = _org(db_session)
    fy = fiscal_year(_INVOICE_DAY)
    numbers = [
        inv.generate_invoice(db_session, org.id, _issued_quote(db_session, org).id,
                             invoice_date=_INVOICE_DAY).number
        for _ in range(3)
    ]
    assert numbers == [f"RV/{fy}/0001", f"RV/{fy}/0002", f"RV/{fy}/0003"]


def test_reinvoicing_a_quote_is_blocked(db_session: Session) -> None:
    org = _org(db_session)
    q = _issued_quote(db_session, org)
    inv.generate_invoice(db_session, org.id, q.id, invoice_date=_INVOICE_DAY)
    with pytest.raises(inv.InvoiceError, match="already invoiced"):
        inv.generate_invoice(db_session, org.id, q.id, invoice_date=_INVOICE_DAY)


def test_only_issued_quote_can_be_invoiced(db_session: Session) -> None:
    org = _org(db_session)
    q = _issued_quote(db_session, org, status="draft")  # a fresh quote is not issued
    with pytest.raises(inv.InvoiceError, match="issued"):
        inv.generate_invoice(db_session, org.id, q.id)


def test_issued_invoice_is_immutable(db_session: Session) -> None:
    org = _org(db_session)
    invoice = inv.generate_invoice(db_session, org.id, _issued_quote(db_session, org).id)
    invoice.total = Decimal("1.00")  # tamper
    with pytest.raises(Exception):  # noqa: B017 — DB trigger raises
        db_session.flush()


def test_credit_note_cancels_and_negates(db_session: Session) -> None:
    org = _org(db_session)
    q = _issued_quote(db_session, org)
    original = inv.generate_invoice(db_session, org.id, q.id, invoice_date=_INVOICE_DAY)

    credit = inv.generate_credit_note(db_session, org.id, original.id,
                                      invoice_date=_INVOICE_DAY, reason="client cancelled")
    assert original.status == "cancelled"
    assert credit.kind == "credit_note"
    assert credit.credit_note_of_id == original.id
    assert credit.number == f"RV/CN/{fiscal_year(_INVOICE_DAY)}/0001"
    assert credit.total == Decimal("-169700.00")
    assert credit.cgst == Decimal("-4040.48")
    assert (credit.taxable + credit.cgst + credit.sgst + credit.igst
            + credit.rounding_adjustment == credit.total)
    # Cancelling frees the quote to be re-invoiced.
    reinvoice = inv.generate_invoice(db_session, org.id, q.id, invoice_date=_INVOICE_DAY)
    assert reinvoice.number == f"RV/{fiscal_year(_INVOICE_DAY)}/0002"


# --- one HTTP pass over the endpoints -------------------------------------- #


@pytest.fixture
def api(db_session: Session) -> Iterator[tuple[TestClient, Organization]]:
    org = _org(db_session)

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_org_id] = lambda: org.id
    try:
        yield TestClient(app), org
    finally:
        app.dependency_overrides.clear()


def test_invoice_endpoints(api: tuple[TestClient, Organization]) -> None:
    client, org = api
    q = _issued_quote(_session_of(client), org)
    gen = client.post(f"/api/v1/quotes/{q.id}/invoice", json={"invoice_date": "2026-08-02"})
    assert gen.status_code == 201, gen.text
    body = gen.json()
    assert body["number"].startswith("RV/2026-27/")
    assert body["total"] == "169700.00"

    inv_id = body["id"]
    assert client.get(f"/api/v1/invoices/{inv_id}").json()["number"] == body["number"]
    listed = client.get(f"/api/v1/projects/{q.project_id}/invoices").json()
    assert any(i["id"] == inv_id for i in listed)

    cn = client.post(f"/api/v1/invoices/{inv_id}/credit-note", json={"reason": "test"})
    assert cn.status_code == 201
    assert cn.json()["total"] == "-169700.00"


def _session_of(client: TestClient) -> Session:
    # The overridden get_session yields the test's db_session.
    gen = app.dependency_overrides[get_session]()
    return next(gen)


# --- PDF ------------------------------------------------------------------- #


def test_indian_formatting_and_words() -> None:
    assert rupees(Decimal("169700.00")) == "Rs. 1,69,700.00"
    assert rupees(Decimal("-169700.00")) == "(Rs. 1,69,700.00)"
    assert amount_in_words(Decimal("169700.00")) == \
        "Rupees One Lakh Sixty Nine Thousand Seven Hundred Only"
    assert amount_in_words(Decimal("-0.50")).startswith("Minus Rupees Zero and Fifty Paise")


def test_render_invoice_pdf(db_session: Session) -> None:
    org = _org(db_session)
    invoice = inv.generate_invoice(db_session, org.id, _issued_quote(db_session, org).id)
    pdf = render_invoice_pdf(invoice, bank_details="HDFC Bank\nA/C 123456789\nIFSC HDFC0000001")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1500


def test_pdf_endpoint(api: tuple[TestClient, Organization]) -> None:
    client, org = api
    q = _issued_quote(_session_of(client), org)
    inv_id = client.post(f"/api/v1/quotes/{q.id}/invoice").json()["id"]
    res = client.get(f"/api/v1/invoices/{inv_id}/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"

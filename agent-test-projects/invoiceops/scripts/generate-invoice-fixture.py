from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "test-fixtures" / "synthetic-invoice.pdf"

NAVY = colors.HexColor("#10293E")
BLUE = colors.HexColor("#2864DC")
PALE_BLUE = colors.HexColor("#EAF1FF")
PALE_RED = colors.HexColor("#FFF0EE")
RED = colors.HexColor("#B53B32")
MUTED = colors.HexColor("#647084")
LINE = colors.HexColor("#DCE1E7")
SOFT = colors.HexColor("#F5F7F9")


def money(value: float) -> str:
    return f"${value:,.2f}"


def page_decor(canvas, document):
    canvas.saveState()
    width, height = letter
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 0.34 * inch, width, 0.34 * inch, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(0.55 * inch, height - 0.22 * inch, "INVOICEOPS SYNTHETIC DOCUMENT FIXTURE")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.55 * inch, 0.35 * inch, "Cloud CUA test data only - no goods or services were provided")
    canvas.drawRightString(width - 0.55 * inch, 0.35 * inch, f"Page {document.page}")
    canvas.restoreState()


def build_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        rightMargin=0.58 * inch,
        leftMargin=0.58 * inch,
        topMargin=0.62 * inch,
        bottomMargin=0.62 * inch,
        title="Synthetic Pacific HVAC Invoice PH-1048",
        author="InvoiceOps test fixture",
        subject="Synthetic invoice for Cloud CUA deployment testing",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=32,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=NAVY,
        spaceBefore=8,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=NAVY,
    )
    small = ParagraphStyle(
        "Small",
        parent=body,
        fontSize=8,
        leading=11,
        textColor=MUTED,
    )
    right = ParagraphStyle(
        "Right",
        parent=body,
        alignment=TA_RIGHT,
    )

    story = []
    story.append(Spacer(1, 0.10 * inch))
    story.append(
        Table(
            [
                [
                    Paragraph("PACIFIC HVAC SERVICES<br/><font size='9' color='#647084'>Synthetic maintenance vendor</font>", title),
                    Paragraph("INVOICE", ParagraphStyle("InvoiceWord", parent=title, alignment=TA_RIGHT, textColor=BLUE)),
                ]
            ],
            colWidths=[4.55 * inch, 2.25 * inch],
        )
    )
    story.append(Spacer(1, 0.10 * inch))
    warning = Table(
        [[Paragraph("SYNTHETIC TEST INVOICE - NOT VALID - DO NOT PAY", ParagraphStyle("Warning", parent=body, fontName="Helvetica-Bold", fontSize=11, textColor=RED, alignment=1))]],
        colWidths=[6.8 * inch],
    )
    warning.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE_RED), ("BOX", (0, 0), (-1, -1), 1.2, RED), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story.append(warning)
    story.append(Spacer(1, 0.20 * inch))

    address_table = Table(
        [
            [Paragraph("FROM", heading), Paragraph("BILL TO", heading), Paragraph("SERVICE PROPERTY", heading)],
            [
                Paragraph("Pacific HVAC Services<br/>100 Test Fixture Avenue<br/>San Francisco, CA 94103<br/>vendor-pacific-hvac", body),
                Paragraph("Northstar Properties<br/>Accounts Payable<br/>200 Demo Ledger Street<br/>San Francisco, CA 94103", body),
                Paragraph("Harbor Center<br/>300 Synthetic Plaza<br/>San Francisco, CA 94105<br/>property-harbor-center", body),
            ],
        ],
        colWidths=[2.27 * inch, 2.27 * inch, 2.26 * inch],
    )
    address_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), SOFT), ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story.append(address_table)
    story.append(Spacer(1, 0.20 * inch))

    metadata = Table(
        [
            [Paragraph("INVOICE NUMBER", small), Paragraph("INVOICE DATE", small), Paragraph("DUE DATE", small), Paragraph("WORK ORDER", small)],
            [Paragraph("PH-1048", body), Paragraph("July 8, 2026", body), Paragraph("July 22, 2026", body), Paragraph("WO-4821", body)],
        ],
        colWidths=[1.7 * inch] * 4,
    )
    metadata.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B9CCF3")), ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CEDAF2")), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.append(metadata)
    story.append(Spacer(1, 0.22 * inch))

    story.append(Paragraph("Invoice line items", heading))
    line_data = [
        ["DESCRIPTION", "QTY", "UNIT PRICE", "AMOUNT"],
        ["Rooftop compressor replacement - RTU-4", "1", money(9200.00), money(9200.00)],
        ["Emergency installation labor", "8", money(325.00), money(2600.00)],
    ]
    lines = Table(line_data, colWidths=[3.85 * inch, 0.6 * inch, 1.1 * inch, 1.25 * inch])
    lines.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (1, 1), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    story.append(lines)
    story.append(Spacer(1, 0.16 * inch))

    totals = Table(
        [
            [Paragraph("Subtotal", right), Paragraph(money(11800.00), right)],
            [Paragraph("Tax (8.25%)", right), Paragraph(money(973.50), right)],
            [Paragraph("TOTAL", ParagraphStyle("TotalLabel", parent=right, fontName="Helvetica-Bold", textColor=colors.white)), Paragraph(money(12773.50), ParagraphStyle("TotalValue", parent=right, fontName="Helvetica-Bold", fontSize=13, textColor=colors.white))],
        ],
        colWidths=[1.35 * inch, 1.15 * inch],
        hAlign="RIGHT",
    )
    totals.setStyle(TableStyle([("BACKGROUND", (0, 2), (-1, 2), NAVY), ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LINEABOVE", (0, 2), (-1, 2), 1, NAVY), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    story.append(totals)
    story.append(Spacer(1, 0.24 * inch))

    story.append(Paragraph("Payment information", heading))
    story.append(Paragraph("TEST PAYMENT DETAILS ONLY. No bank account, routing number, tax identifier, or real payment instruction is present in this document. Submit through the InvoiceOps synthetic workflow only.", body))

    story.append(PageBreak())
    story.append(Spacer(1, 0.10 * inch))
    story.append(Paragraph("Service detail and extraction ground truth", title))
    story.append(Paragraph("This second page intentionally exercises multi-page asynchronous expense analysis. All names, identifiers, addresses, and amounts are synthetic.", body))
    story.append(Spacer(1, 0.16 * inch))

    details = Table(
        [
            ["SERVICE FIELD", "SYNTHETIC VALUE"],
            ["Service date", "July 7, 2026"],
            ["Equipment", "Rooftop unit RTU-4"],
            ["Technician", "Taylor Demo"],
            ["Service location", "Harbor Center - roof mechanical area"],
            ["Work order", "WO-4821"],
            ["Authorization", "Synthetic approval reference AUTH-TEST-221"],
        ],
        colWidths=[2.1 * inch, 4.7 * inch],
    )
    details.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9)]))
    story.append(details)
    story.append(Spacer(1, 0.24 * inch))

    story.append(Paragraph("Expected Textract expense fields", heading))
    ground_truth = [
        ["FIELD", "EXPECTED VALUE"],
        ["VENDOR_NAME", "Pacific HVAC Services"],
        ["INVOICE_RECEIPT_ID", "PH-1048"],
        ["INVOICE_RECEIPT_DATE", "07/08/2026"],
        ["DUE_DATE", "07/22/2026"],
        ["SUBTOTAL", "11800.00"],
        ["TAX", "973.50"],
        ["TOTAL", "12773.50"],
        ["PO_NUMBER", "WO-4821"],
    ]
    ground_table = Table(ground_truth, colWidths=[2.65 * inch, 4.15 * inch])
    ground_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Courier"), ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9)]))
    story.append(ground_table)
    story.append(Spacer(1, 0.24 * inch))

    second_warning = Table(
        [[Paragraph("SYNTHETIC TEST INVOICE - NOT VALID - NEVER SUBMIT FOR PAYMENT", ParagraphStyle("SecondWarning", parent=body, fontName="Helvetica-Bold", fontSize=12, textColor=RED, alignment=1))]],
        colWidths=[6.8 * inch],
    )
    second_warning.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE_RED), ("BOX", (0, 0), (-1, -1), 1.2, RED), ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14)]))
    story.append(second_warning)

    document.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    build_pdf()

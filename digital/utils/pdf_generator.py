from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from io import BytesIO
from django.http import HttpResponse


def generate_summary_pdf(summary, title=None):
    """
    Generate a PDF for a single ChapterSummary.
    Returns HttpResponse with the PDF.
    """
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{title or "summary"}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=20,
        spaceAfter=20,
        alignment=TA_LEFT,
    )
    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=6,
        spaceBefore=12,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )

    story = []

    # Title
    if summary.chapter_title:
        story.append(Paragraph(f"<b>{summary.chapter_title}</b>", title_style))

    # Book info
    story.append(Paragraph(f"<i>From: {summary.book.title}</i>", body_style))
    if summary.book.author:
        story.append(Paragraph(f"<i>Author: {summary.book.author}</i>", body_style))
    if summary.category:
        story.append(Paragraph(f"<i>Category: {summary.category.name}</i>", body_style))
    story.append(Spacer(1, 0.2 * inch))

    # Sections
    sections = [
        ("Main Idea", summary.main_idea),
        ("Key Lessons", summary.key_lessons),
        ("Important Concepts", summary.concepts),
        ("Examples", summary.examples),
        ("Action Steps", summary.actions),
        ("Personal Insight", summary.personal_insight),
    ]

    for label, content in sections:
        if content:
            story.append(Paragraph(f"<b>{label}</b>", heading_style))
            story.append(Paragraph(content.replace("\n", "<br/>"), body_style))
            story.append(Spacer(1, 0.1 * inch))

    doc.build(story)
    return response


def generate_category_summary_pdf(summaries, category_name):
    """
    Generate a PDF for all summaries in a category.
    Returns HttpResponse with the PDF.
    """
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{category_name}_summaries.pdf"'
    )

    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=22,
        spaceAfter=20,
        alignment=TA_LEFT,
    )
    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=6,
        spaceBefore=12,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )

    story = []
    story.append(Paragraph(f"<b>{category_name} – Summaries</b>", title_style))
    story.append(Spacer(1, 0.2 * inch))

    for idx, summary in enumerate(summaries, 1):
        story.append(
            Paragraph(
                f"<b>{idx}. {summary.chapter_title or 'Untitled'}</b>", heading_style
            )
        )
        story.append(Paragraph(f"<i>From: {summary.book.title}</i>", body_style))
        if summary.book.author:
            story.append(Paragraph(f"<i>Author: {summary.book.author}</i>", body_style))
        story.append(Spacer(1, 0.1 * inch))

        sections = [
            ("Main Idea", summary.main_idea),
            ("Key Lessons", summary.key_lessons),
            ("Important Concepts", summary.concepts),
            ("Examples", summary.examples),
            ("Action Steps", summary.actions),
            ("Personal Insight", summary.personal_insight),
        ]
        for label, content in sections:
            if content:
                story.append(Paragraph(f"<b>{label}</b>", heading_style))
                story.append(Paragraph(content.replace("\n", "<br/>"), body_style))
                story.append(Spacer(1, 0.1 * inch))
        story.append(Spacer(1, 0.3 * inch))
        story.append(PageBreak())

    doc.build(story)
    return response

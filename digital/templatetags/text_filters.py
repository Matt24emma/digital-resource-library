from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()


@register.filter
def smart_paragraphs(text):
    """
    Converts text into paragraphs intelligently:
    - If the text already contains HTML tags (like <p>, <div>, etc.), return it as safe.
    - Otherwise, split plain text into paragraphs and wrap each in <p> tags.
    """
    if not text:
        return ""

    # Check if the text contains any HTML tags
    if re.search(r"<[^>]+>", text):
        # Already HTML, return as safe
        return mark_safe(text)

    # Plain text: split into paragraphs
    if "\n\n" in text:
        paragraphs = text.split("\n\n")
    elif "\n" in text:
        paragraphs = text.split("\n")
    else:
        # Split into sentences and group them into paragraphs of ~3 sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        paragraphs = []
        for i in range(0, len(sentences), 3):
            paragraphs.append(" ".join(sentences[i : i + 3]))

    # Wrap each paragraph in <p> tags
    return mark_safe(
        "".join(f"<p>{para.strip()}</p>" for para in paragraphs if para.strip())
    )

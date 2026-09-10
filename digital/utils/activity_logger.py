from digital.models import ActivityLog


def log_activity(user, action, details=None, book=None, summary=None):
    try:
        if not user or not user.is_authenticated:
            return

        # Build a descriptive string
        desc_parts = []
        if details:
            if isinstance(details, dict):
                desc_parts.append(", ".join(f"{k}: {v}" for k, v in details.items()))
            else:
                desc_parts.append(str(details))
        if book:
            desc_parts.append(f"Book: {book.title}")
        if summary:
            desc_parts.append(f"Summary: {summary.chapter_title}")
        description = " | ".join(desc_parts) if desc_parts else ""

        ActivityLog.objects.create(
            user=user,
            action=action,
            description=description,
        )
    except Exception as e:
        print(f"Activity log failed: {e}")

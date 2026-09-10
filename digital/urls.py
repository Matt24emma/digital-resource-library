from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ============================================================
    # AUTHENTICATION & ACCOUNT
    # ============================================================
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("create-account/", views.create_account, name="create_account"),
    path("reset-session/", views.reset_session, name="reset_session"),
    path("landingpage", views.landingpage, name="landingpage"),
    # Password Reset
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="digital/password_reset_form.html",
            email_template_name="digital/password_reset_email.html",
            subject_template_name="digital/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="digital/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="digital/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="digital/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    # Change password
    path(
        "change-password/",
        views.change_password,
        name="change_password",
    ),
    # Email verification
    path(
        "verify/<str:token>/",
        views.verify_email,
        name="verify_email",
    ),
    path(
        "verification-sent/",
        views.verification_sent,
        name="verification_sent",
    ),
    path(
        "resend-verification/",
        views.resend_verification,
        name="resend_verification",
    ),
    # ============================================================
    # USER DASHBOARD FEATURES
    # ============================================================
    path("", views.home, name="home"),
    path(
        "user_dashboard/",
        views.user_dashboard,
        name="user_dashboard",
    ),
    # Reading plans
    path(
        "reading/",
        views.reading_plans,
        name="reading_plans",
    ),
    # Summaries
    path(
        "summaries/",
        views.all_summaries,
        name="all_summaries",
    ),
    path(
        "summaries/edit/<int:pk>/",
        views.edit_summary,
        name="edit_summary",
    ),
    path(
        "summaries/delete/<int:pk>/",
        views.delete_summary,
        name="delete_summary",
    ),
    path(
        "scheduled-books/",
        views.scheduled_books,
        name="scheduled_books",
    ),
    path(
        "send-chunk/<int:chunk_id>/",
        views.send_chunk_now,
        name="send_chunk_now",
    ),
    # Categories
    path(
        "categories/",
        views.manage_categories,
        name="manage_categories",
    ),
    path(
        "categories/create/",
        views.create_category,
        name="create_category",
    ),
    path(
        "categories/delete/<int:pk>/",
        views.delete_category,
        name="delete_category",
    ),
    # Book & summary creation
    path(
        "summaryForm/",
        views.summaryForm,
        name="summaryForm",
    ),
    path(
        "summary",
        views.summary,
        name="summary",
    ),
    # Review & cards
    path(
        "review/<int:pk>/",
        views.review,
        name="review",
    ),
    path(
        "knowledge-cards/<int:pk>/",
        views.generate_cards,
        name="generate_cards",
    ),
    path(
        "download-card/<int:pk>/",
        views.download_card,
        name="download_card",
    ),
    # Library and reading
    path(
        "library/",
        views.library,
        name="library",
    ),
    path(
        "reading_session/",
        views.reading_session,
        name="reading_session",
    ),
    path(
        "book_details/",
        views.book_details,
        name="book_details",
    ),
    path(
        "chapter_summary/",
        views.chapter_summary,
        name="chapter_summary",
    ),
    path(
        "card_manager/",
        views.card_manager,
        name="card_manager",
    ),
    path("product", views.product, name="product"),
    path(
        "pdf_export",
        views.pdf_export,
        name="pdf_export",
    ),
    # ============================================================
    # SUBSCRIPTION & PAYMENTS
    # ============================================================
    path(
        "pricing/",
        views.pricing,
        name="pricing",
    ),
    path(
        "upgrade/",
        views.initialize_payment,
        name="initialize_payment",
    ),
    path(
        "payment/callback/",
        views.payment_callback,
        name="payment_callback",
    ),
    path(
        "payment_billing",
        views.payment_billing,
        name="payment_billing",
    ),
    # digital/urls.py (additions)
    path("save-card/<int:pk>/", views.save_card_image, name="save_card_image"),
    path(
        "download-card-png/<int:pk>/", views.download_card_png, name="download_card_png"
    ),
    path("recent-cards/", views.recent_cards, name="recent_cards"),
    # ============================================================
    # PROFILE & SETTINGS
    # ============================================================
    path(
        "profile",
        views.profile,
        name="profile",
    ),
    path(
        "settings/",
        views.setting,
        name="setting",
    ),
    path(
        "activity",
        views.activity,
        name="activity",
    ),
    path(
        "categories/<int:category_id>/contents/",
        views.category_contents,
        name="category_contents",
    ),
    path(
        "categories/edit/<int:category_id>/", views.edit_category, name="edit_category"
    ),
    path(
        "Resources/summaries/delete/<int:pk>/",
        views.delete_summary,
        name="delete_summary",
    ),
    path("Resources/delete-book/<int:pk>/", views.delete_book, name="delete_book"),
    # ============================================================
    # EXPORT & BOOK MANAGEMENT
    # ============================================================
    path(
        "update-pages/<int:book_id>/", views.update_pages_per_day, name="update_pages"
    ),
    path("preferences/update/", views.update_preferences, name="update_preferences"),
    path("schedule/add/<int:book_id>/", views.add_to_schedule, name="add_to_schedule"),
    path(
        "export-pdf/<int:pk>/",
        views.export_summary_pdf,
        name="export_summary_pdf",
    ),
    path(
        "export-category-pdf/<int:category_id>/",
        views.export_category_pdf,
        name="export_category_pdf",
    ),
    path(
        "delete-book/<int:book_id>/",
        views.delete_scheduled_book,
        name="delete_book",
    ),
    path("activity_admin", views.activity_admin, name="activity_admin"),
    path("schedule/add/<int:book_id>/", views.add_to_schedule, name="add_to_schedule"),
    path(
        "schedule/remove/<int:book_id>/",
        views.remove_from_schedule,
        name="remove_from_schedule",
    ),
    path("paystack/webhook/", views.paystack_webhook, name="paystack_webhook"),
    path("export-leads-pdf/", views.export_leads_pdf, name="export_leads_pdf"),
    path(
        "reading-plan/<int:book_id>/", views.book_reading_plan, name="book_reading_plan"
    ),
    path(
        "mark-chunk-read/<int:chunk_id>/", views.mark_chunk_read, name="mark_chunk_read"
    ),
    path("activity/", views.activity, name="activity"),
    path("activity/export/", views.export_activity, name="export_activity"),
    path("activity/<int:pk>/", views.activity_detail, name="activity_detail"),
    path("schedule/add/<int:book_id>/", views.add_to_schedule, name="add_to_schedule"),
    # ============================================================
    # ADMIN RESOURCE MANAGEMENT
    # ============================================================
    # These MUST come before <slug:slug>/ because <slug:slug> is
    # a catch-all route.
    path(
        "admin/",
        views.admin,
        name="admin",
    ),
    path(
        "edit/<int:id>/",
        views.edit_resource,
        name="edit_resource",
    ),
    path(
        "delete/<int:id>/",
        views.delete_resource,
        name="delete_resource",
    ),
    # ============================================================
    # ADMIN-ONLY DASHBOARD PAGES
    # ============================================================
    path(
        "downloads",
        views.downloads,
        name="downloads",
    ),
    path("delete-account/", views.delete_account, name="delete_account"),
    path(
        "user_management",
        views.user_management,
        name="user_management",
    ),
    path(
        "subscript_management/",
        views.subscript_management,
        name="subscript_management",
    ),
    path(
        "revenue",
        views.revenue,
        name="revenue",
    ),
    path(
        "ai_usage",
        views.AI_usage,
        name="ai_usage",
    ),
    path(
        "book_analytic",
        views.book_analytic,
        name="book_analytic",
    ),
    path(
        "knowledge_card",
        views.knowledge_card,
        name="knowledge_card",
    ),
    path(
        "payments",
        views.payments,
        name="payments",
    ),
    path(
        "system_settings",
        views.system_settings,
        name="system_settings",
    ),
    path(
        "admin_support",
        views.admin_support,
        name="admin_support",
    ),
    path(
        "reading-plan/<int:book_id>/", views.book_reading_plan, name="book_reading_plan"
    ),
    path(
        "mark-chunk-read/<int:chunk_id>/", views.mark_chunk_read, name="mark_chunk_read"
    ),
    path("schedule/add/<int:book_id>/", views.add_to_schedule, name="add_to_schedule"),
    # ============================================================
    # RESOURCE & DOWNLOAD
    # ============================================================
    # Specific resource URLs MUST come before the catch-all.
    path(
        "download/<slug:slug>/",
        views.download_resource,
        name="download_resource",
    ),
    path(
        "leads/<slug:slug>/",
        views.leads,
        name="leads",
    ),
    # ============================================================
    # RESOURCE DETAIL — CATCH-ALL
    # ============================================================
    # Keep this LAST.
    path(
        "<slug:slug>/",
        views.resource_detail,
        name="resource_detail",
    ),
]

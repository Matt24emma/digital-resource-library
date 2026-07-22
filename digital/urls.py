from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("admin/", views.admin, name="admin"),
    path("leads/", views.leads, name="leads"),
    path("downloads", views.downloads, name="downloads"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("reset-session/", views.reset_session, name="reset_session"),
    path("create-account/", views.create_account, name="create_account"),
    path("<slug:slug>/", views.resource_detail, name="resource_detail"),
    path("edit/<int:id>/", views.edit_resource, name="edit_resource"),
    path("leads/<slug:slug>/", views.leads, name="leads"),
    path("delete/<int:id>/", views.delete_resource, name="delete_resource"),
    path("download/<slug:slug>/", views.download_resource, name="download_resource"),
]

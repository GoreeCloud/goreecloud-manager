"""URL configuration for GoreeCloud Manager."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core.forms import ThrottledAdminAuthenticationForm, ThrottledAuthenticationForm

# The Django admin is part of the same private administrative authority boundary. Reuse
# the shared throttle while retaining AdminAuthenticationForm's active/staff checks.
admin.site.login_form = ThrottledAdminAuthenticationForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="core/login.html",
            authentication_form=ThrottledAuthenticationForm,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("core.urls")),
]

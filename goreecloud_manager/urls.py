"""URL configuration for GoreeCloud Manager."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core.forms import ThrottledAuthenticationForm

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

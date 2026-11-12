from django.urls import path

from . import views

urlpatterns = [
    path("register", views.RegisterView.as_view(), name="auth-register"),
    path("me", views.MeView.as_view(), name="auth-me"),
    path("login", views.LoginView.as_view(), name="auth-login"),
    path("token/refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout", views.LogoutView.as_view(), name="auth-logout"),
]
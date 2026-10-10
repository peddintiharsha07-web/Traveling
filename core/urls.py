from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import LoginForm, StyledPasswordChangeForm, StyledPasswordResetForm, StyledSetPasswordForm

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("destinations/", views.destination_list, name="destinations"),
    path("destinations/<slug:slug>/", views.destination_detail, name="destination_detail"),
    path("travel-problems/", views.problem_list, name="problems"),
    path("travel-problems/<slug:slug>/", views.problem_detail, name="problem_detail"),

    # Accounts
    path("login/", auth_views.LoginView.as_view(
        template_name="core/login.html", authentication_form=LoginForm, redirect_authenticated_user=True,
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # POST only
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("profile/password/", auth_views.PasswordChangeView.as_view(
        template_name="core/password_change.html", form_class=StyledPasswordChangeForm,
        success_url=reverse_lazy("core:profile"),
    ), name="password_change"),

    # Password reset by email (the console email backend prints the link in development)
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="core/password_reset_form.html", form_class=StyledPasswordResetForm,
        email_template_name="core/emails/password_reset_email.txt",
        subject_template_name="core/emails/password_reset_subject.txt",
        success_url=reverse_lazy("core:password_reset_done"),
    ), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="core/password_reset_done.html",
    ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="core/password_reset_confirm.html", form_class=StyledSetPasswordForm,
        success_url=reverse_lazy("core:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="core/password_reset_complete.html",
    ), name="password_reset_complete"),

    # Reports and dashboard
    path("dashboard/", views.dashboard, name="dashboard"),
    path("reports/new/", views.report_create, name="report_create"),
    path("reports/<int:pk>/", views.report_detail, name="report_detail"),
    path("reports/<int:pk>/edit/", views.report_edit, name="report_edit"),
    path("reports/<int:pk>/delete/", views.report_delete, name="report_delete"),
    path("reports/<int:pk>/image/", views.report_image, name="report_image"),
    path("community/", views.community, name="community"),

    # Notifications and activity
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read-all/", views.notifications_mark_read, name="notifications_mark_read"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),

    # Help and information
    path("find-help/", views.find_help, name="find_help"),
    path("search/", views.search, name="search"),
    path("contact/", views.contact, name="contact"),
    path("about/", views.about, name="about"),
]

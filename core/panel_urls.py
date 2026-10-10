from django.urls import path

from . import panel_views as v

app_name = "panel"

urlpatterns = [
    path("login/", v.PanelLoginView.as_view(), name="login"),
    path("", v.dashboard, name="dashboard"),

    path("users/", v.user_list, name="user_list"),
    path("users/<int:pk>/edit/", v.user_edit, name="user_edit"),
    path("users/<int:pk>/toggle/", v.user_toggle, name="user_toggle"),
    path("users/<int:pk>/delete/", v.user_delete, name="user_delete"),

    path("destinations/", v.destination_list, name="destination_list"),
    path("destinations/new/", v.destination_create, name="destination_create"),
    path("destinations/<int:pk>/edit/", v.destination_edit, name="destination_edit"),
    path("destinations/<int:pk>/delete/", v.destination_delete, name="destination_delete"),

    path("problems/", v.problem_list, name="problem_list"),
    path("problems/new/", v.problem_create, name="problem_create"),
    path("problems/<int:pk>/edit/", v.problem_edit, name="problem_edit"),
    path("problems/<int:pk>/delete/", v.problem_delete, name="problem_delete"),

    path("reports/", v.report_list, name="report_list"),
    path("reports/<int:pk>/", v.report_manage, name="report_manage"),
    path("reports/<int:pk>/delete/", v.report_delete, name="report_delete"),
    path("replies/<int:pk>/delete/", v.reply_delete, name="reply_delete"),

    path("messages/", v.message_list, name="message_list"),
    path("messages/<int:pk>/", v.message_detail, name="message_detail"),
    path("messages/<int:pk>/delete/", v.message_delete, name="message_delete"),

    path("activity/", v.activity_list, name="activity_list"),
]

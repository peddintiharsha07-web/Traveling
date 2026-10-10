from django.contrib import admin

from .models import (
    ActivityLog, ContactMessage, Destination, Problem, ProblemReport, Profile, ReportResponse, Notification,
)


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("name", "place", "category", "featured")
    list_filter = ("category", "featured")
    search_fields = ("name", "place")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "order")
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}


class ReportResponseInline(admin.TabularInline):
    model = ReportResponse
    extra = 0


@admin.register(ProblemReport)
class ProblemReportAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "category", "status", "share_with_community", "created_at")
    list_filter = ("status", "category", "share_with_community")
    list_editable = ("status",)
    search_fields = ("title", "location", "user__username")
    readonly_fields = ("user", "created_at", "updated_at")
    inlines = [ReportResponseInline]


admin.site.register(Profile)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("subject", "name", "email", "message")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("user__username", "message")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "detail")
    search_fields = ("user__username", "action", "detail")
    readonly_fields = ("user", "action", "detail", "created_at")

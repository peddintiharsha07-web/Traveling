"""Staff-only admin panel. Every view is wrapped in @staff_required."""
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView, redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import AdminLoginForm, DestinationForm, PanelReportForm, PanelUserForm, ProblemForm
from .models import (
    ActivityLog, ContactMessage, Destination, Problem, ProblemReport, ReportResponse,
)
from .notify import log_activity, notify
from .views import paginate

User = get_user_model()
PER_PAGE = 12


# ---------------------------------------------------------------------------
# Access control and shared helpers
# ---------------------------------------------------------------------------

def staff_required(view):
    """Anonymous users go to the panel login; signed-in non-staff users get a 403."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse("panel:login"))
        if not (request.user.is_active and request.user.is_staff):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


class PanelLoginView(LoginView):
    template_name = "panel/login.html"
    authentication_form = AdminLoginForm
    redirect_authenticated_user = False

    def get_success_url(self):
        return self.get_redirect_url() or reverse("panel:dashboard")


def render_panel(request, template, section, **context):
    context.update({
        "section": section,
        "nav_unread_messages": ContactMessage.objects.filter(is_read=False).count(),
        "nav_new_reports": ProblemReport.objects.filter(status=ProblemReport.Status.SUBMITTED).count(),
    })
    return render(request, template, context)


def back_to(request, default):
    """Redirect to a same-site 'next' URL when given, otherwise to the default route name."""
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                   require_https=request.is_secure()):
        return redirect(target)
    return redirect(default)


def pick(value, allowed, default=""):
    return value if value in allowed else default


def delete_report_images(reports):
    for report in reports:
        if report.image:
            report.image.delete(save=False)


def can_manage(actor, target):
    """Only superusers may manage administrators; anyone may manage their own account."""
    if target.pk == actor.pk:
        return True
    if target.is_staff or target.is_superuser:
        return actor.is_superuser
    return True


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@staff_required
def dashboard(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    reports = ProblemReport.objects

    status_rows = {r["status"]: r["n"] for r in reports.values("status").annotate(n=Count("id"))}
    status_cards = [
        {"key": key, "label": label, "n": status_rows.get(key, 0)} for key, label in ProblemReport.Status.choices
    ]

    labels = dict(ProblemReport.CATEGORY_CHOICES)
    cat_rows = list(reports.values("category").annotate(n=Count("id")).order_by("-n")[:6])
    top = max([r["n"] for r in cat_rows], default=1) or 1
    categories = [
        {"label": labels.get(r["category"], r["category"]), "n": r["n"], "pct": round(r["n"] * 100 / top)}
        for r in cat_rows
    ]

    start = timezone.localdate() - timedelta(days=6)
    day_rows = (
        reports.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id")).order_by("day")
    )
    by_day = {r["day"]: r["n"] for r in day_rows}
    daily = [{"day": start + timedelta(days=i), "n": by_day.get(start + timedelta(days=i), 0)} for i in range(7)]
    day_top = max([d["n"] for d in daily], default=1) or 1
    for d in daily:
        d["pct"] = round(d["n"] * 100 / day_top)

    unread = ContactMessage.objects.filter(is_read=False).count()
    new_reports = status_rows.get(ProblemReport.Status.SUBMITTED, 0)
    stats = {
        "users": User.objects.count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "new_users": User.objects.filter(date_joined__gte=week_ago).count(),
        "reports": sum(status_rows.values()),
        "new_reports_week": reports.filter(created_at__gte=week_ago).count(),
        "open_reports": new_reports + status_rows.get(ProblemReport.Status.IN_REVIEW, 0),
        "destinations": Destination.objects.count(),
        "problems": Problem.objects.count(),
        "replies": ReportResponse.objects.count(),
        "messages": ContactMessage.objects.count(),
    }
    alerts = []
    if new_reports:
        alerts.append({"text": f"{new_reports} new report{'s' if new_reports != 1 else ''} waiting for review.",
                       "url": reverse("panel:report_list") + "?status=submitted"})
    if unread:
        alerts.append({"text": f"{unread} unread contact message{'s' if unread != 1 else ''}.",
                       "url": reverse("panel:message_list") + "?status=unread"})

    return render_panel(request, "panel/dashboard.html", "dashboard",
                        stats=stats, status_cards=status_cards, categories=categories, daily=daily, alerts=alerts,
                        recent_reports=reports.select_related("user")[:6],
                        recent_users=User.objects.order_by("-date_joined")[:6],
                        recent_messages=ContactMessage.objects.all()[:5])


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

USER_SORTS = {"newest": "-date_joined", "oldest": "date_joined", "name": "username", "reports": "-report_count"}


@staff_required
def user_list(request):
    q = request.GET.get("q", "").strip()[:80]
    status = pick(request.GET.get("status"), {"active", "inactive"})
    role = pick(request.GET.get("role"), {"staff", "member"})
    sort = pick(request.GET.get("sort"), USER_SORTS, "newest")

    users = User.objects.annotate(report_count=Count("reports", distinct=True))
    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q)
                             | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    if status:
        users = users.filter(is_active=(status == "active"))
    if role:
        users = users.filter(is_staff=(role == "staff"))
    page_obj, qs = paginate(request, users.order_by(USER_SORTS[sort], "pk"), PER_PAGE)
    return render_panel(request, "panel/user_list.html", "users", page_obj=page_obj, qs=qs, q=q,
                        status=status, role=role, sort=sort, sorts=USER_SORTS, total=page_obj.paginator.count)


@staff_required
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    if not can_manage(request.user, target):
        raise PermissionDenied
    form = PanelUserForm(request.POST or None, instance=target, actor=request.user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            log_activity(request.user, "Panel: edited user", target.username)
            messages.success(request, f"Saved changes to {target.username}.")
            return redirect("panel:user_list")
        messages.error(request, "Fix the highlighted fields and try again.")
    return render_panel(request, "panel/form.html", "users", form=form, title=f"Edit user: {target.username}",
                        back_url=reverse("panel:user_list"), submit="Save user", obj=target,
                        reports=target.reports.all()[:8])


@staff_required
@require_POST
def user_toggle(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
    elif not can_manage(request.user, target):
        raise PermissionDenied
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        word = "activated" if target.is_active else "deactivated"
        log_activity(request.user, f"Panel: {word} user", target.username)
        messages.success(request, f"{target.username} was {word}.")
    return back_to(request, "panel:user_list")


@staff_required
@require_POST
def user_delete(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "You cannot delete your own account here.")
    elif not can_manage(request.user, target):
        raise PermissionDenied
    else:
        name = target.username
        delete_report_images(target.reports.exclude(image=""))
        target.delete()
        log_activity(request.user, "Panel: deleted user", name)
        messages.success(request, f"User {name} and their reports were deleted.")
    return redirect("panel:user_list")


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------

DEST_SORTS = {"name": "name", "newest": "-id", "place": "place", "featured": "-featured"}


@staff_required
def destination_list(request):
    q = request.GET.get("q", "").strip()[:80]
    category = pick(request.GET.get("category"), Destination.Category.values)
    featured = pick(request.GET.get("featured"), {"yes", "no"})
    sort = pick(request.GET.get("sort"), DEST_SORTS, "name")

    items = Destination.objects.all()
    if q:
        items = items.filter(Q(name__icontains=q) | Q(place__icontains=q) | Q(blurb__icontains=q))
    if category:
        items = items.filter(category=category)
    if featured:
        items = items.filter(featured=(featured == "yes"))
    page_obj, qs = paginate(request, items.order_by(DEST_SORTS[sort], "pk"), PER_PAGE)
    return render_panel(request, "panel/destination_list.html", "destinations", page_obj=page_obj, qs=qs, q=q,
                        category=category, featured=featured, sort=sort, sorts=DEST_SORTS,
                        categories=Destination.Category.choices, total=page_obj.paginator.count)


@staff_required
def destination_create(request):
    form = DestinationForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            log_activity(request.user, "Panel: added destination", obj.name)
            messages.success(request, f"Destination “{obj.name}” added.")
            return redirect("panel:destination_list")
        messages.error(request, "Fix the highlighted fields and try again.")
    return render_panel(request, "panel/form.html", "destinations", form=form, title="Add a destination",
                        back_url=reverse("panel:destination_list"), submit="Add destination", multipart=True,
                        slug_source="id_name")


@staff_required
def destination_edit(request, pk):
    obj = get_object_or_404(Destination, pk=pk)
    form = DestinationForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            log_activity(request.user, "Panel: edited destination", obj.name)
            messages.success(request, f"Destination “{obj.name}” saved.")
            return redirect("panel:destination_list")
        messages.error(request, "Fix the highlighted fields and try again.")
    return render_panel(request, "panel/form.html", "destinations", form=form, title=f"Edit: {obj.name}",
                        back_url=reverse("panel:destination_list"), submit="Save destination", multipart=True,
                        obj=obj, view_url=obj.get_absolute_url())


@staff_required
@require_POST
def destination_delete(request, pk):
    obj = get_object_or_404(Destination, pk=pk)
    name = obj.name
    if obj.image:
        obj.image.delete(save=False)
    obj.delete()
    log_activity(request.user, "Panel: deleted destination", name)
    messages.success(request, f"Destination “{name}” deleted.")
    return back_to(request, "panel:destination_list")


# ---------------------------------------------------------------------------
# Problem guides
# ---------------------------------------------------------------------------

PROBLEM_SORTS = {"order": "order", "title": "title", "newest": "-id"}


@staff_required
def problem_list(request):
    q = request.GET.get("q", "").strip()[:80]
    sort = pick(request.GET.get("sort"), PROBLEM_SORTS, "order")
    items = Problem.objects.all()
    if q:
        items = items.filter(Q(title__icontains=q) | Q(blurb__icontains=q))
    page_obj, qs = paginate(request, items.order_by(PROBLEM_SORTS[sort], "pk"), PER_PAGE)
    return render_panel(request, "panel/problem_list.html", "problems", page_obj=page_obj, qs=qs, q=q,
                        sort=sort, sorts=PROBLEM_SORTS, total=page_obj.paginator.count)


@staff_required
def problem_create(request):
    form = ProblemForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            log_activity(request.user, "Panel: added problem guide", obj.title)
            messages.success(request, f"Guide “{obj.title}” added.")
            return redirect("panel:problem_list")
        messages.error(request, "Fix the highlighted fields and try again.")
    return render_panel(request, "panel/form.html", "problems", form=form, title="Add a problem guide",
                        back_url=reverse("panel:problem_list"), submit="Add guide", slug_source="id_title")


@staff_required
def problem_edit(request, pk):
    obj = get_object_or_404(Problem, pk=pk)
    form = ProblemForm(request.POST or None, instance=obj)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            log_activity(request.user, "Panel: edited problem guide", obj.title)
            messages.success(request, f"Guide “{obj.title}” saved.")
            return redirect("panel:problem_list")
        messages.error(request, "Fix the highlighted fields and try again.")
    return render_panel(request, "panel/form.html", "problems", form=form, title=f"Edit: {obj.title}",
                        back_url=reverse("panel:problem_list"), submit="Save guide", obj=obj,
                        view_url=obj.get_absolute_url())


@staff_required
@require_POST
def problem_delete(request, pk):
    obj = get_object_or_404(Problem, pk=pk)
    title = obj.title
    obj.delete()
    log_activity(request.user, "Panel: deleted problem guide", title)
    messages.success(request, f"Guide “{title}” deleted.")
    return back_to(request, "panel:problem_list")


# ---------------------------------------------------------------------------
# Reports and replies
# ---------------------------------------------------------------------------

REPORT_SORTS = {"newest": "-created_at", "oldest": "created_at", "updated": "-updated_at", "status": "status"}


@staff_required
def report_list(request):
    q = request.GET.get("q", "").strip()[:80]
    status = pick(request.GET.get("status"), ProblemReport.Status.values)
    category = pick(request.GET.get("category"), dict(ProblemReport.CATEGORY_CHOICES))
    shared = pick(request.GET.get("shared"), {"yes", "no"})
    sort = pick(request.GET.get("sort"), REPORT_SORTS, "newest")

    items = ProblemReport.objects.select_related("user").annotate(reply_count=Count("responses"))
    if q:
        items = items.filter(Q(title__icontains=q) | Q(location__icontains=q) | Q(user__username__icontains=q)
                             | Q(description__icontains=q))
    if status:
        items = items.filter(status=status)
    if category:
        items = items.filter(category=category)
    if shared:
        items = items.filter(share_with_community=(shared == "yes"))
    page_obj, qs = paginate(request, items.order_by(REPORT_SORTS[sort], "-pk"), PER_PAGE)
    return render_panel(request, "panel/report_list.html", "reports", page_obj=page_obj, qs=qs, q=q,
                        status=status, category=category, shared=shared, sort=sort, sorts=REPORT_SORTS,
                        statuses=ProblemReport.Status.choices, categories=ProblemReport.CATEGORY_CHOICES,
                        total=page_obj.paginator.count)


@staff_required
def report_manage(request, pk):
    report = get_object_or_404(ProblemReport.objects.select_related("user"), pk=pk)
    form = PanelReportForm(request.POST or None, instance=report)
    if request.method == "POST":
        if form.is_valid():
            changed = set(form.changed_data)
            report = form.save()
            if changed:
                parts = []
                if "status" in changed:
                    parts.append(f"is now “{report.get_status_display().lower()}”")
                if "staff_note" in changed and report.staff_note:
                    parts.append("has a new update from our team")
                if parts:
                    notify(report.user, f"Your report “{report.title}” " + " and ".join(parts) + ".",
                           report.get_absolute_url())
                log_activity(request.user, "Panel: updated report", report.title)
            messages.success(request, "Report updated." if changed else "No changes to save.")
            return redirect("panel:report_manage", pk=report.pk)
        messages.error(request, "Fix the highlighted fields and try again.")
    return render_panel(request, "panel/report_manage.html", "reports", report=report, form=form,
                        responses=report.responses.select_related("author"))


@staff_required
@require_POST
def report_delete(request, pk):
    report = get_object_or_404(ProblemReport, pk=pk)
    title = report.title
    delete_report_images([report])
    report.delete()
    log_activity(request.user, "Panel: deleted report", title)
    messages.success(request, f"Report “{title}” deleted.")
    return redirect("panel:report_list")


@staff_required
@require_POST
def reply_delete(request, pk):
    reply = get_object_or_404(ReportResponse, pk=pk)
    report_pk = reply.report_id
    reply.delete()
    log_activity(request.user, "Panel: removed a reply", f"report #{report_pk}")
    messages.success(request, "Reply removed.")
    return redirect("panel:report_manage", pk=report_pk)


# ---------------------------------------------------------------------------
# Contact messages
# ---------------------------------------------------------------------------

@staff_required
def message_list(request):
    q = request.GET.get("q", "").strip()[:80]
    status = pick(request.GET.get("status"), {"unread", "read"})
    items = ContactMessage.objects.select_related("user")
    if q:
        items = items.filter(Q(subject__icontains=q) | Q(name__icontains=q) | Q(email__icontains=q)
                             | Q(message__icontains=q))
    if status:
        items = items.filter(is_read=(status == "read"))
    page_obj, qs = paginate(request, items, PER_PAGE)
    return render_panel(request, "panel/message_list.html", "messages", page_obj=page_obj, qs=qs, q=q,
                        status=status, total=page_obj.paginator.count)


@staff_required
def message_detail(request, pk):
    msg = get_object_or_404(ContactMessage.objects.select_related("user"), pk=pk)
    if not msg.is_read:
        msg.is_read = True
        msg.save(update_fields=["is_read"])
    return render_panel(request, "panel/message_detail.html", "messages", msg=msg)


@staff_required
@require_POST
def message_delete(request, pk):
    msg = get_object_or_404(ContactMessage, pk=pk)
    msg.delete()
    log_activity(request.user, "Panel: deleted a contact message")
    messages.success(request, "Message deleted.")
    return redirect("panel:message_list")


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------

@staff_required
def activity_list(request):
    q = request.GET.get("q", "").strip()[:80]
    items = ActivityLog.objects.select_related("user")
    if q:
        items = items.filter(Q(user__username__icontains=q) | Q(action__icontains=q) | Q(detail__icontains=q))
    page_obj, qs = paginate(request, items, 25)
    return render_panel(request, "panel/activity_list.html", "activity", page_obj=page_obj, qs=qs, q=q,
                        total=page_obj.paginator.count)

import mimetypes

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import data
from .forms import ContactForm, ProfileForm, RegisterForm, ReportForm, ResponseForm, UserForm
from .models import ActivityLog, Destination, Problem, ProblemReport, Profile
from .notify import log_activity, notify

DESTINATIONS_PER_PAGE = 9
REPORTS_PER_PAGE = 10


def paginate(request, queryset, per_page):
    """Returns (page_obj, querystring_without_page) for the shared pager partial."""
    page_obj = Paginator(queryset, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page_obj, params.urlencode()


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

def home(request):
    context = {
        "destinations": Destination.objects.all()[:6],
        "problems": Problem.objects.all(),
        "help_types": data.HELP_TYPES,
        "tips": data.SAFETY_TIPS,
        "steps": data.STEPS,
        "stories": data.STORIES,
    }
    return render(request, "core/home.html", context)


def destination_list(request):
    q = request.GET.get("q", "").strip()[:80]
    category = request.GET.get("category", "")
    if category not in Destination.Category.values:
        category = ""

    destinations = Destination.objects.all()
    if category:
        destinations = destinations.filter(category=category)
    if q:
        destinations = destinations.filter(
            Q(name__icontains=q) | Q(place__icontains=q) | Q(blurb__icontains=q)
        )

    page_obj, qs = paginate(request, destinations, DESTINATIONS_PER_PAGE)
    return render(request, "core/destination_list.html", {
        "destinations": page_obj,
        "page_obj": page_obj,
        "qs": qs,
        "total": page_obj.paginator.count,
        "q": q,
        "category": category,
        "categories": Destination.Category.choices,
    })


def destination_detail(request, slug):
    destination = get_object_or_404(Destination, slug=slug)
    related = Destination.objects.filter(category=destination.category).exclude(pk=destination.pk)[:3]
    return render(request, "core/destination_detail.html", {"d": destination, "related": related})


def problem_list(request):
    return render(request, "core/problem_list.html", {"problems": Problem.objects.all()})


def problem_detail(request, slug):
    problem = get_object_or_404(Problem, slug=slug)
    others = Problem.objects.exclude(pk=problem.pk)
    return render(request, "core/problem_detail.html", {"p": problem, "others": others})


def find_help(request):
    selected = request.GET.get("type", "")
    if selected not in {h["key"] for h in data.HELP_TYPES}:
        selected = "hospital"
    return render(request, "core/find_help.html", {
        "help_types": data.HELP_TYPES,
        "selected": selected,
        "map_config": settings.MAP_CONFIG,
    })


def about(request):
    return render(request, "core/about.html")


def contact(request):
    initial = {}
    if request.user.is_authenticated:
        initial = {"name": request.user.get_full_name() or request.user.username, "email": request.user.email}
    form = ContactForm(request.POST or None, initial=initial)
    if request.method == "POST":
        if form.is_valid():
            if form.cleaned_data.get("website"):
                # Honeypot was filled in: pretend it worked, store nothing.
                messages.success(request, "Thanks. Your message has been sent.")
                return redirect("core:contact")
            msg = form.save(commit=False)
            if request.user.is_authenticated:
                msg.user = request.user
            msg.save()
            if request.user.is_authenticated:
                log_activity(request.user, "Sent a contact message", msg.subject)
            messages.success(request, "Thanks. Your message has been sent and our team will read it soon.")
            return redirect("core:contact")
        messages.error(request, "Fix the highlighted fields and try again.")
    return render(request, "core/contact.html", {"form": form})


def search(request):
    q = request.GET.get("q", "").strip()[:80]
    results = {"destinations": [], "problems": [], "reports": []}
    if len(q) >= 2:
        results["destinations"] = list(Destination.objects.filter(
            Q(name__icontains=q) | Q(place__icontains=q) | Q(blurb__icontains=q) | Q(description__icontains=q)
        )[:12])
        results["problems"] = list(Problem.objects.filter(
            Q(title__icontains=q) | Q(blurb__icontains=q) | Q(overview__icontains=q)
        )[:12])
        if request.user.is_authenticated:
            visible = Q(user=request.user) | Q(share_with_community=True)
            if request.user.is_staff:
                visible = Q()
            results["reports"] = list(
                ProblemReport.objects.filter(visible)
                .filter(Q(title__icontains=q) | Q(location__icontains=q) | Q(description__icontains=q))
                .select_related("user")[:12]
            )
    total = sum(len(v) for v in results.values())
    return render(request, "core/search.html", {
        "q": q, "results": results, "total": total, "too_short": bool(q) and len(q) < 2,
    })


def csrf_failure(request, reason=""):
    return render(request, "403.html", {"csrf_problem": True}, status=403)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def register(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        Profile.objects.get_or_create(user=user)
        login(request, user)
        log_activity(user, "Created an account")
        notify(user, "Welcome aboard. Add your home country on your profile so we can tailor tips.",
               reverse("core:profile"))
        messages.success(request, "Welcome aboard. Your account is ready.")
        return redirect("core:dashboard")
    return render(request, "core/register.html", {"form": form})


@login_required
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    user_form = UserForm(request.POST or None, instance=request.user, prefix="user")
    profile_form = ProfileForm(request.POST or None, instance=profile_obj, prefix="profile")
    if request.method == "POST":
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            log_activity(request.user, "Updated profile")
            messages.success(request, "Profile saved.")
            return redirect("core:profile")
        messages.error(request, "Fix the highlighted fields and try again.")
    return render(request, "core/profile.html", {"user_form": user_form, "profile_form": profile_form})


# ---------------------------------------------------------------------------
# Reports (all views require login; each checks ownership or sharing)
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    own = ProblemReport.objects.filter(user=request.user)
    status_counts = {row["status"]: row["n"] for row in own.values("status").annotate(n=Count("id"))}
    counts = {
        "total": sum(status_counts.values()),
        "open": status_counts.get(ProblemReport.Status.SUBMITTED, 0) + status_counts.get(ProblemReport.Status.IN_REVIEW, 0),
        "resolved": status_counts.get(ProblemReport.Status.RESOLVED, 0),
    }

    status = request.GET.get("status", "")
    if status not in ProblemReport.Status.values:
        status = ""
    reports = own.annotate(reply_count=Count("responses"))
    if status:
        reports = reports.filter(status=status)
    page_obj, qs = paginate(request, reports, REPORTS_PER_PAGE)

    return render(request, "core/dashboard.html", {
        "reports": page_obj,
        "page_obj": page_obj,
        "qs": qs,
        "counts": counts,
        "status": status,
        "statuses": ProblemReport.Status.choices,
        "recent_notifications": request.user.notifications.all()[:4],
        "recent_activity": request.user.activity.all()[:5],
    })


@login_required
def report_create(request):
    initial = {}
    preset = request.GET.get("category", "")
    if preset in dict(ProblemReport.CATEGORY_CHOICES):
        initial["category"] = preset

    if request.method == "POST":
        form = ReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.save()
            log_activity(request.user, "Submitted a report", report.title)
            messages.success(request, "Report submitted. You can follow its status here.")
            return redirect(report)
        messages.error(request, "Fix the highlighted fields and try again.")
    else:
        form = ReportForm(initial=initial)
    return render(request, "core/report_form.html", {"form": form, "editing": False})


@login_required
def report_edit(request, pk):
    report = get_object_or_404(ProblemReport, pk=pk, user=request.user)  # others get a 404
    if not report.can_be_edited_by(request.user):
        messages.error(request, "This report is already being reviewed, so it can no longer be edited.")
        return redirect(report)

    form = ReportForm(request.POST or None, request.FILES or None, instance=report)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            log_activity(request.user, "Edited a report", report.title)
            messages.success(request, "Report updated.")
            return redirect(report)
        messages.error(request, "Fix the highlighted fields and try again.")
    return render(request, "core/report_form.html", {"form": form, "editing": True, "report": report})


@login_required
@require_POST
def report_delete(request, pk):
    report = get_object_or_404(ProblemReport, pk=pk, user=request.user)
    title = report.title
    if report.image:
        report.image.delete(save=False)
    report.delete()
    log_activity(request.user, "Deleted a report", title)
    messages.success(request, "Report deleted.")
    return redirect("core:dashboard")


@login_required
def report_detail(request, pk):
    report = get_object_or_404(ProblemReport.objects.select_related("user"), pk=pk)
    if not report.can_be_viewed_by(request.user):
        raise Http404  # do not reveal that a private report exists

    form = ResponseForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            reply = form.save(commit=False)
            reply.report = report
            reply.author = request.user
            reply.save()
            if report.user_id != request.user.id:
                notify(report.user, f"{request.user.username} replied to your report \"{report.title}\".",
                       report.get_absolute_url())
            log_activity(request.user, "Posted a reply", report.title)
            messages.success(request, "Reply posted.")
            return redirect(report)
        messages.error(request, "Your reply could not be posted.")

    return render(request, "core/report_detail.html", {
        "r": report,
        "responses": report.responses.select_related("author"),
        "form": form,
        "is_owner": report.user_id == request.user.id,
        "can_edit": report.can_be_edited_by(request.user),
    })


@login_required
def report_image(request, pk):
    report = get_object_or_404(ProblemReport, pk=pk)
    if not report.image or not report.can_be_viewed_by(request.user):
        raise Http404
    content_type = mimetypes.guess_type(report.image.name)[0] or "application/octet-stream"
    return FileResponse(report.image.open("rb"), content_type=content_type)


@login_required
def community(request):
    q = request.GET.get("q", "").strip()[:80]
    category = request.GET.get("category", "")
    if category not in dict(ProblemReport.CATEGORY_CHOICES):
        category = ""

    reports = (
        ProblemReport.objects.filter(share_with_community=True)
        .select_related("user")
        .annotate(reply_count=Count("responses"))
    )
    if category:
        reports = reports.filter(category=category)
    if q:
        reports = reports.filter(Q(title__icontains=q) | Q(location__icontains=q) | Q(description__icontains=q))

    page_obj, qs = paginate(request, reports, REPORTS_PER_PAGE)
    return render(request, "core/community.html", {
        "reports": page_obj, "page_obj": page_obj, "qs": qs, "q": q, "category": category,
        "categories": ProblemReport.CATEGORY_CHOICES, "total": page_obj.paginator.count,
    })


# ---------------------------------------------------------------------------
# Notifications and activity history
# ---------------------------------------------------------------------------

@login_required
def notifications(request):
    page_obj, qs = paginate(request, request.user.notifications.all(), 15)
    activity = ActivityLog.objects.filter(user=request.user)[:15]
    return render(request, "core/notifications.html", {
        "notifications": page_obj, "page_obj": page_obj, "qs": qs, "activity": activity,
    })


@login_required
def notification_open(request, pk):
    """Marks one notification read, then sends the user to the page it points to."""
    note = get_object_or_404(request.user.notifications, pk=pk)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=["is_read"])
    safe = note.url.startswith("/") and not note.url.startswith("//")
    return redirect(note.url if safe else "core:notifications")


@login_required
@require_POST
def notifications_mark_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("core:notifications")

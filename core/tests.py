from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Destination, Problem, ProblemReport

User = get_user_model()


def make_report(user, **kwargs):
    defaults = dict(
        title="Lost bag", category="lost-luggage-documents", description="My bag did not arrive.",
        location="Lisbon airport", date_of_problem=timezone.localdate(),
    )
    defaults.update(kwargs)
    return ProblemReport.objects.create(user=user, **defaults)


class PublicPageTests(TestCase):
    def setUp(self):
        Destination.objects.create(name="Swiss Alps", slug="swiss-alps", place="Switzerland",
                                   category="mountains", blurb="High peaks.")
        Destination.objects.create(name="Bali", slug="bali", place="Indonesia",
                                   category="beaches", blurb="Surf and temples.")
        Problem.objects.create(title="Lost luggage", slug="lost-luggage", blurb="b", overview="o",
                               steps="One\nTwo", contacts="Airline", keep_as_proof="Receipt", prevention="Label it")

    def test_core_pages_load(self):
        for name in ("core:home", "core:destinations", "core:problems", "core:find_help", "core:about",
                     "core:login", "core:register"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_destination_search_and_filter(self):
        r = self.client.get(reverse("core:destinations"), {"q": "alps"})
        self.assertContains(r, "Swiss Alps")
        self.assertNotContains(r, "Surf and temples")
        r = self.client.get(reverse("core:destinations"), {"category": "beaches"})
        self.assertContains(r, "Bali")
        self.assertNotContains(r, "High peaks")

    def test_unknown_category_is_ignored(self):
        r = self.client.get(reverse("core:destinations"), {"category": "nonsense"})
        self.assertContains(r, "Swiss Alps")
        self.assertContains(r, "Bali")

    def test_problem_detail_and_missing_page(self):
        self.assertContains(self.client.get(reverse("core:problem_detail", args=["lost-luggage"])), "Two")
        self.assertEqual(self.client.get("/travel-problems/nope/").status_code, 404)

    def test_custom_404_page(self):
        r = self.client.get("/definitely-not-here/")
        self.assertContains(r, "Page not found", status_code=404)

    def test_find_help_exposes_map_config_not_secrets(self):
        r = self.client.get(reverse("core:find_help"), {"type": "police"})
        self.assertContains(r, 'id="map-config"')
        self.assertContains(r, 'data-type="police"')


class AccountTests(TestCase):
    def test_register_logs_user_in(self):
        r = self.client.post(reverse("core:register"), {
            "username": "ana", "email": "ana@example.com",
            "password1": "S0me-long-pass!", "password2": "S0me-long-pass!",
        })
        self.assertRedirects(r, reverse("core:dashboard"))
        self.assertTrue(User.objects.filter(username="ana").exists())

    def test_duplicate_email_rejected(self):
        User.objects.create_user("bo", "bo@example.com", "pw-12345-xyz")
        r = self.client.post(reverse("core:register"), {
            "username": "bo2", "email": "BO@example.com",
            "password1": "S0me-long-pass!", "password2": "S0me-long-pass!",
        })
        self.assertContains(r, "already exists")

    def test_dashboard_requires_login(self):
        r = self.client.get(reverse("core:dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("core:login"), r["Location"])

    def test_logout_requires_post(self):
        user = User.objects.create_user("cy", "cy@example.com", "pw-12345-xyz")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("core:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("core:logout")).status_code, 302)


class ReportPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "o@example.com", "pw-12345-xyz")
        self.other = User.objects.create_user("other", "x@example.com", "pw-12345-xyz")
        self.private = make_report(self.owner, title="Private one")
        self.shared = make_report(self.owner, title="Shared one", share_with_community=True)

    def test_owner_sees_private_report(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.private.get_absolute_url()).status_code, 200)

    def test_other_user_cannot_see_private_report(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.private.get_absolute_url()).status_code, 404)

    def test_other_user_can_see_and_reply_to_shared_report(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.shared.get_absolute_url()).status_code, 200)
        r = self.client.post(self.shared.get_absolute_url(), {"body": "Call the airline desk."})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.shared.responses.count(), 1)

    def test_other_user_cannot_reply_to_private_report(self):
        self.client.force_login(self.other)
        r = self.client.post(self.private.get_absolute_url(), {"body": "Hello there"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.private.responses.count(), 0)

    def test_dashboard_lists_only_own_reports(self):
        make_report(self.other, title="Someone else's report")
        self.client.force_login(self.owner)
        r = self.client.get(reverse("core:dashboard"))
        self.assertContains(r, "Private one")
        self.assertNotContains(r, "Someone else")

    def test_anonymous_cannot_view_report(self):
        r = self.client.get(self.shared.get_absolute_url())
        self.assertEqual(r.status_code, 302)

    def test_future_date_rejected(self):
        self.client.force_login(self.owner)
        r = self.client.post(reverse("core:report_create"), {
            "title": "Future", "category": "weather", "description": "Storm",
            "location": "Oslo", "date_of_problem": (timezone.localdate() + timedelta(days=3)).isoformat(),
        })
        self.assertContains(r, "cannot be in the future")
        self.assertFalse(ProblemReport.objects.filter(title="Future").exists())

    def test_create_report(self):
        self.client.force_login(self.owner)
        r = self.client.post(reverse("core:report_create"), {
            "title": "Delayed train", "category": "transport-delays", "description": "Two hours late",
            "location": "Milan", "date_of_problem": timezone.localdate().isoformat(),
        })
        report = ProblemReport.objects.get(title="Delayed train")
        self.assertRedirects(r, report.get_absolute_url())
        self.assertEqual(report.user, self.owner)
        self.assertFalse(report.share_with_community)


# ---------------------------------------------------------------------------
# Admin panel, user panel extras, and supporting features
# ---------------------------------------------------------------------------

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import ActivityLog, ContactMessage, Notification, ReportResponse

PASSWORD = "pw-12345-xyz"


def make_staff(username="boss", superuser=False):
    user = User.objects.create_user(username, f"{username}@example.com", PASSWORD, is_staff=True)
    if superuser:
        user.is_superuser = True
        user.save()
    return user


PANEL_LIST_URLS = (
    "panel:dashboard", "panel:user_list", "panel:destination_list", "panel:problem_list",
    "panel:report_list", "panel:message_list", "panel:activity_list",
    "panel:destination_create", "panel:problem_create",
)


class PanelAccessTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user("member", "m@example.com", PASSWORD)
        self.staff = make_staff()

    def test_anonymous_is_sent_to_panel_login(self):
        for name in PANEL_LIST_URLS:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn(reverse("panel:login"), r["Location"], name)

    def test_regular_user_gets_403_everywhere(self):
        self.client.force_login(self.member)
        for name in PANEL_LIST_URLS:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_regular_user_cannot_post_panel_actions(self):
        self.client.force_login(self.member)
        target = User.objects.create_user("victim", "v@example.com", PASSWORD)
        self.assertEqual(self.client.post(reverse("panel:user_delete", args=[target.pk])).status_code, 403)
        self.assertTrue(User.objects.filter(pk=target.pk).exists())

    def test_staff_can_open_every_panel_page(self):
        self.client.force_login(self.staff)
        for name in PANEL_LIST_URLS:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_panel_login_rejects_non_staff(self):
        r = self.client.post(reverse("panel:login"), {"username": "member", "password": PASSWORD})
        self.assertContains(r, "administrators only")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_panel_login_accepts_staff(self):
        r = self.client.post(reverse("panel:login"), {"username": "boss", "password": PASSWORD})
        self.assertRedirects(r, reverse("panel:dashboard"))

    def test_staff_link_only_shown_to_staff(self):
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(reverse("core:home")), "Admin panel")
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("core:home")), "Admin panel")


class PanelUserManagementTests(TestCase):
    def setUp(self):
        self.staff = make_staff("staffer")
        self.root = make_staff("root", superuser=True)
        self.member = User.objects.create_user("traveler", "t@example.com", PASSWORD)

    def test_search_and_filter_users(self):
        User.objects.create_user("zed", "zed@example.com", PASSWORD, is_active=False)
        self.client.force_login(self.staff)
        r = self.client.get(reverse("panel:user_list"), {"q": "trav"})
        self.assertContains(r, ">traveler</a>")
        self.assertNotContains(r, ">zed</a>")
        r = self.client.get(reverse("panel:user_list"), {"status": "inactive"})
        self.assertContains(r, ">zed</a>")
        self.assertNotContains(r, ">traveler</a>")

    def test_deactivate_and_reactivate(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("panel:user_toggle", args=[self.member.pk]))
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.client.post(reverse("panel:user_toggle", args=[self.member.pk]))
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_deactivated_user_cannot_log_in(self):
        self.member.is_active = False
        self.member.save()
        r = self.client.post(reverse("core:login"), {"username": "traveler", "password": PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_delete_user_removes_their_reports(self):
        make_report(self.member)
        self.client.force_login(self.staff)
        self.client.post(reverse("panel:user_delete", args=[self.member.pk]))
        self.assertFalse(User.objects.filter(pk=self.member.pk).exists())
        self.assertEqual(ProblemReport.objects.count(), 0)

    def test_delete_requires_post(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("panel:user_delete", args=[self.member.pk])).status_code, 405)

    def test_cannot_delete_or_deactivate_self(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("panel:user_delete", args=[self.staff.pk]))
        self.client.post(reverse("panel:user_toggle", args=[self.staff.pk]))
        self.staff.refresh_from_db()
        self.assertTrue(User.objects.filter(pk=self.staff.pk).exists())
        self.assertTrue(self.staff.is_active)

    def test_plain_staff_cannot_manage_other_administrators(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse("panel:user_delete", args=[self.root.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("panel:user_edit", args=[self.root.pk])).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.root.pk).exists())

    def test_superuser_can_manage_administrators(self):
        self.client.force_login(self.root)
        self.assertEqual(self.client.get(reverse("panel:user_edit", args=[self.staff.pk])).status_code, 200)

    def test_only_superuser_sees_administrator_checkbox(self):
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(reverse("panel:user_edit", args=[self.member.pk])), "is_staff")
        self.client.force_login(self.root)
        self.assertContains(self.client.get(reverse("panel:user_edit", args=[self.member.pk])), "is_staff")

    def test_plain_staff_cannot_promote_via_forged_post(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("panel:user_edit", args=[self.member.pk]), {
            "username": "traveler", "first_name": "", "last_name": "", "email": "t@example.com",
            "is_active": "on", "is_staff": "on",
        })
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_staff)

    def test_edit_user_rejects_duplicate_email(self):
        User.objects.create_user("other", "taken@example.com", PASSWORD)
        self.client.force_login(self.staff)
        r = self.client.post(reverse("panel:user_edit", args=[self.member.pk]), {
            "username": "traveler", "email": "taken@example.com", "is_active": "on",
        })
        self.assertContains(r, "already uses this email")


class PanelContentTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.client.force_login(self.staff)

    def test_destination_crud(self):
        r = self.client.post(reverse("panel:destination_create"), {
            "name": "Fjords", "slug": "fjords", "place": "Norway", "category": "mountains",
            "blurb": "Deep blue water.", "description": "", "travel_tip": "",
        })
        self.assertRedirects(r, reverse("panel:destination_list"))
        dest = Destination.objects.get(slug="fjords")
        self.client.post(reverse("panel:destination_edit", args=[dest.pk]), {
            "name": "Norwegian Fjords", "slug": "fjords", "place": "Norway", "category": "mountains",
            "blurb": "Deep blue water.", "featured": "on",
        })
        dest.refresh_from_db()
        self.assertEqual(dest.name, "Norwegian Fjords")
        self.assertTrue(dest.featured)
        self.assertEqual(self.client.get(reverse("panel:destination_delete", args=[dest.pk])).status_code, 405)
        self.client.post(reverse("panel:destination_delete", args=[dest.pk]))
        self.assertFalse(Destination.objects.filter(pk=dest.pk).exists())

    def test_destination_validation_errors_are_shown(self):
        r = self.client.post(reverse("panel:destination_create"), {"name": "", "slug": "", "place": "", "category": ""})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "This field is required")
        self.assertEqual(Destination.objects.count(), 0)

    def test_destination_rejects_fake_image(self):
        fake = SimpleUploadedFile("evil.png", b"<script>alert(1)</script>", content_type="image/png")
        r = self.client.post(reverse("panel:destination_create"), {
            "name": "X", "slug": "x", "place": "Y", "category": "beaches", "blurb": "b", "image": fake,
        })
        self.assertContains(r, "valid image")
        self.assertEqual(Destination.objects.count(), 0)

    def test_problem_crud(self):
        data = {"title": "Lost phone", "slug": "lost-phone", "icon": "compass", "blurb": "b", "overview": "o",
                "steps": "One\nTwo", "contacts": "Carrier", "keep_as_proof": "Receipt", "prevention": "Lock it",
                "order": 3}
        self.assertRedirects(self.client.post(reverse("panel:problem_create"), data), reverse("panel:problem_list"))
        problem = Problem.objects.get(slug="lost-phone")
        data["title"] = "Lost or stolen phone"
        self.client.post(reverse("panel:problem_edit", args=[problem.pk]), data)
        problem.refresh_from_db()
        self.assertEqual(problem.title, "Lost or stolen phone")
        self.client.post(reverse("panel:problem_delete", args=[problem.pk]))
        self.assertFalse(Problem.objects.filter(pk=problem.pk).exists())

    def test_destination_list_filters_sorts_and_paginates(self):
        for i in range(15):
            Destination.objects.create(name=f"Place {i:02d}", slug=f"place-{i}", place="Nowhere",
                                       category="beaches", blurb="b")
        Destination.objects.create(name="Alps", slug="alps", place="Swiss", category="mountains", blurb="b")
        r = self.client.get(reverse("panel:destination_list"))
        self.assertEqual(len(r.context["page_obj"]), 12)
        r = self.client.get(reverse("panel:destination_list"), {"page": 2})
        self.assertEqual(len(r.context["page_obj"]), 4)
        r = self.client.get(reverse("panel:destination_list"), {"category": "mountains"})
        self.assertContains(r, "Alps")
        self.assertNotContains(r, "Place 01")
        r = self.client.get(reverse("panel:destination_list"), {"sort": "bogus"})
        self.assertEqual(r.status_code, 200)  # unknown sort falls back safely


class PanelReportTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.owner = User.objects.create_user("owner", "o@example.com", PASSWORD)
        self.report = make_report(self.owner, title="Late bus")
        self.client.force_login(self.staff)

    def test_status_change_notifies_owner(self):
        r = self.client.post(reverse("panel:report_manage", args=[self.report.pk]),
                             {"status": "resolved", "staff_note": "Refund issued."})
        self.assertRedirects(r, reverse("panel:report_manage", args=[self.report.pk]))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "resolved")
        note = Notification.objects.get(user=self.owner)
        self.assertIn("Late bus", note.message)
        self.assertIn("resolved", note.message)

    def test_saving_without_changes_sends_no_notification(self):
        self.client.post(reverse("panel:report_manage", args=[self.report.pk]),
                         {"status": "submitted", "staff_note": ""})
        self.assertEqual(Notification.objects.count(), 0)

    def test_report_list_filters(self):
        make_report(self.owner, title="Other problem", status="resolved")
        r = self.client.get(reverse("panel:report_list"), {"status": "resolved"})
        self.assertContains(r, "Other problem")
        self.assertNotContains(r, "Late bus")
        r = self.client.get(reverse("panel:report_list"), {"q": "late"})
        self.assertContains(r, "Late bus")

    def test_delete_reply_and_report(self):
        reply = ReportResponse.objects.create(report=self.report, author=self.owner, body="Spam spam spam")
        self.client.post(reverse("panel:reply_delete", args=[reply.pk]))
        self.assertEqual(ReportResponse.objects.count(), 0)
        self.client.post(reverse("panel:report_delete", args=[self.report.pk]))
        self.assertEqual(ProblemReport.objects.count(), 0)

    def test_dashboard_shows_alert_for_new_reports(self):
        r = self.client.get(reverse("panel:dashboard"))
        self.assertContains(r, "1 new report waiting for review")


class ContactTests(TestCase):
    def test_contact_form_saves_message(self):
        r = self.client.post(reverse("core:contact"), {
            "name": "Ana", "email": "ana@example.com", "subject": "Hello",
            "message": "I would love a guide about visas.",
        })
        self.assertRedirects(r, reverse("core:contact"))
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_short_message_rejected(self):
        r = self.client.post(reverse("core:contact"), {
            "name": "Ana", "email": "ana@example.com", "subject": "Hello", "message": "Hi",
        })
        self.assertContains(r, "at least a short sentence")
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_honeypot_discards_bot_messages(self):
        self.client.post(reverse("core:contact"), {
            "name": "Bot", "email": "bot@example.com", "subject": "Buy now",
            "message": "Cheap pills and more cheap pills", "website": "http://spam.example",
        })
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_staff_reads_message_and_it_is_marked_read(self):
        msg = ContactMessage.objects.create(name="Ana", email="ana@example.com", subject="Hello",
                                            message="A long enough message.")
        self.client.force_login(make_staff())
        self.assertContains(self.client.get(reverse("panel:message_list")), "Hello")
        self.assertContains(self.client.get(reverse("panel:message_detail", args=[msg.pk])), "A long enough message.")
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)


class UserReportManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "o@example.com", PASSWORD)
        self.other = User.objects.create_user("other", "x@example.com", PASSWORD)
        self.report = make_report(self.owner, title="Original title")

    def edit_payload(self, **extra):
        data = {"title": "New title", "category": "weather", "description": "Changed",
                "location": "Oslo", "date_of_problem": timezone.localdate().isoformat()}
        data.update(extra)
        return data

    def test_owner_can_edit_submitted_report(self):
        self.client.force_login(self.owner)
        r = self.client.post(reverse("core:report_edit", args=[self.report.pk]), self.edit_payload())
        self.assertRedirects(r, self.report.get_absolute_url())
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, "New title")

    def test_edit_blocked_once_in_review(self):
        self.report.status = ProblemReport.Status.IN_REVIEW
        self.report.save()
        self.client.force_login(self.owner)
        r = self.client.post(reverse("core:report_edit", args=[self.report.pk]), self.edit_payload())
        self.assertRedirects(r, self.report.get_absolute_url())
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, "Original title")

    def test_other_user_cannot_edit_or_delete(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("core:report_edit", args=[self.report.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("core:report_delete", args=[self.report.pk])).status_code, 404)
        self.assertTrue(ProblemReport.objects.filter(pk=self.report.pk).exists())

    def test_owner_can_delete_with_post_only(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("core:report_delete", args=[self.report.pk])).status_code, 405)
        r = self.client.post(reverse("core:report_delete", args=[self.report.pk]))
        self.assertRedirects(r, reverse("core:dashboard"))
        self.assertFalse(ProblemReport.objects.filter(pk=self.report.pk).exists())

    def test_fake_image_upload_is_rejected(self):
        self.client.force_login(self.owner)
        fake = SimpleUploadedFile("photo.png", b"not really an image", content_type="image/png")
        r = self.client.post(reverse("core:report_create"), {
            "title": "With photo", "category": "weather", "description": "Storm", "location": "Oslo",
            "date_of_problem": timezone.localdate().isoformat(), "image": fake,
        })
        self.assertContains(r, "valid image")
        self.assertFalse(ProblemReport.objects.filter(title="With photo").exists())

    def test_dashboard_status_filter_and_pagination(self):
        for i in range(12):
            make_report(self.owner, title=f"Extra {i}", status="resolved")
        self.client.force_login(self.owner)
        r = self.client.get(reverse("core:dashboard"), {"status": "resolved"})
        self.assertEqual(len(r.context["reports"]), 10)
        self.assertNotContains(r, "Original title")
        r = self.client.get(reverse("core:dashboard"), {"status": "resolved", "page": 2})
        self.assertEqual(len(r.context["reports"]), 2)


class NotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "o@example.com", PASSWORD)
        self.helper = User.objects.create_user("helper", "h@example.com", PASSWORD)
        self.report = make_report(self.owner, title="Shared", share_with_community=True)

    def test_reply_notifies_owner_but_not_self(self):
        self.client.force_login(self.helper)
        self.client.post(self.report.get_absolute_url(), {"body": "Try the airline desk."})
        self.assertEqual(Notification.objects.filter(user=self.owner).count(), 1)
        self.client.force_login(self.owner)
        self.client.post(self.report.get_absolute_url(), {"body": "Thanks, that worked!"})
        self.assertEqual(Notification.objects.filter(user=self.owner).count(), 1)

    def test_open_marks_read_and_redirects(self):
        note = Notification.objects.create(user=self.owner, message="Hi", url=self.report.get_absolute_url())
        self.client.force_login(self.owner)
        r = self.client.get(reverse("core:notification_open", args=[note.pk]))
        self.assertRedirects(r, self.report.get_absolute_url())
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_unsafe_notification_url_is_ignored(self):
        note = Notification.objects.create(user=self.owner, message="Hi", url="//evil.example/phish")
        self.client.force_login(self.owner)
        r = self.client.get(reverse("core:notification_open", args=[note.pk]))
        self.assertRedirects(r, reverse("core:notifications"))

    def test_cannot_open_someone_elses_notification(self):
        note = Notification.objects.create(user=self.owner, message="Private")
        self.client.force_login(self.helper)
        self.assertEqual(self.client.get(reverse("core:notification_open", args=[note.pk])).status_code, 404)

    def test_mark_all_read(self):
        Notification.objects.create(user=self.owner, message="One")
        Notification.objects.create(user=self.owner, message="Two")
        self.client.force_login(self.owner)
        self.client.post(reverse("core:notifications_mark_read"))
        self.assertEqual(self.owner.notifications.filter(is_read=False).count(), 0)

    def test_notifications_page_and_unread_badge(self):
        Notification.objects.create(user=self.owner, message="Your report moved")
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("core:notifications")), "Your report moved")
        self.assertContains(self.client.get(reverse("core:home")), "count-pill")

    def test_login_is_recorded_in_activity(self):
        self.client.post(reverse("core:login"), {"username": "owner", "password": PASSWORD})
        self.assertTrue(ActivityLog.objects.filter(user=self.owner, action="Logged in").exists())


class SearchAndPaginationTests(TestCase):
    def setUp(self):
        Destination.objects.create(name="Swiss Alps", slug="swiss-alps", place="Switzerland",
                                   category="mountains", blurb="High peaks.")
        Problem.objects.create(title="Lost passport", slug="lost-passport", blurb="Replace it fast.",
                               overview="o", steps="One", contacts="Embassy", keep_as_proof="Copy", prevention="Scan")
        self.owner = User.objects.create_user("owner", "o@example.com", PASSWORD)
        self.other = User.objects.create_user("other", "x@example.com", PASSWORD)
        make_report(self.owner, title="Passport stolen", location="Rome")
        make_report(self.owner, title="Passport shared", location="Paris", share_with_community=True)

    def test_search_finds_destinations_and_guides(self):
        r = self.client.get(reverse("core:search"), {"q": "alps"})
        self.assertContains(r, "Swiss Alps")
        r = self.client.get(reverse("core:search"), {"q": "passport"})
        self.assertContains(r, "Lost passport")

    def test_search_hides_private_reports_from_others(self):
        self.client.force_login(self.other)
        r = self.client.get(reverse("core:search"), {"q": "passport"})
        self.assertContains(r, "Passport shared")
        self.assertNotContains(r, "Passport stolen")

    def test_anonymous_search_never_returns_reports(self):
        r = self.client.get(reverse("core:search"), {"q": "passport"})
        self.assertNotContains(r, "Passport shared")

    def test_short_query_is_handled(self):
        self.assertContains(self.client.get(reverse("core:search"), {"q": "a"}), "at least two characters")

    def test_public_destination_pagination(self):
        for i in range(10):
            Destination.objects.create(name=f"Spot {i}", slug=f"spot-{i}", place="Here", category="beaches", blurb="b")
        r = self.client.get(reverse("core:destinations"))
        self.assertEqual(len(r.context["destinations"]), 9)
        self.assertContains(r, "Page 1 of 2")
        r = self.client.get(reverse("core:destinations"), {"page": 2})
        self.assertEqual(len(r.context["destinations"]), 2)

    def test_community_search(self):
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse("core:community"), {"q": "paris"}), "Passport shared")
        self.assertNotContains(self.client.get(reverse("core:community"), {"q": "zzzz"}), "Passport shared")


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", "ana@example.com", PASSWORD)

    def test_reset_pages_load(self):
        for name in ("core:password_reset", "core:password_reset_done", "core:password_reset_complete"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_reset_email_sent_for_known_address(self):
        r = self.client.post(reverse("core:password_reset"), {"email": "ana@example.com"})
        self.assertRedirects(r, reverse("core:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/reset/", mail.outbox[0].body)

    def test_unknown_address_gets_same_response_without_email(self):
        r = self.client.post(reverse("core:password_reset"), {"email": "nobody@example.com"})
        self.assertRedirects(r, reverse("core:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_full_reset_flow(self):
        self.client.post(reverse("core:password_reset"), {"email": "ana@example.com"})
        link = [line for line in mail.outbox[0].body.splitlines() if "/reset/" in line][0].strip()
        path = "/" + link.split("://", 1)[1].split("/", 1)[1]
        r = self.client.get(path, follow=True)  # Django swaps the token for a session URL
        self.assertEqual(r.status_code, 200)
        post_url = r.redirect_chain[-1][0]
        r = self.client.post(post_url, {"new_password1": "Brand-new-pass-77!", "new_password2": "Brand-new-pass-77!"})
        self.assertRedirects(r, reverse("core:password_reset_complete"))
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password("Brand-new-pass-77!"))

    def test_login_page_links_to_reset(self):
        self.assertContains(self.client.get(reverse("core:login")), reverse("core:password_reset"))

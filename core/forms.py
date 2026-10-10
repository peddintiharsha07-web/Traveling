from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm, UserCreationForm,
)
from django.utils import timezone

from .models import ContactMessage, Destination, Problem, ProblemReport, Profile, ReportResponse

User = get_user_model()

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image(image):
    """Validate a fresh upload: size limit plus real image content (not just the file name)."""
    # Only fresh uploads (UploadedFile objects have a content_type) need checking.
    if image and hasattr(image, "content_type"):
        if image.size > MAX_IMAGE_BYTES:
            raise forms.ValidationError("The image is larger than 5 MB.")
        fmt = getattr(getattr(image, "image", None), "format", None)
        if fmt not in ALLOWED_IMAGE_FORMATS:
            raise forms.ValidationError("Upload a JPEG, PNG, or WebP image.")
    return image


class StyledFormMixin:
    """Adds the site's input classes to every widget."""

    def _style(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "check"
            elif isinstance(widget, forms.FileInput):
                widget.attrs["class"] = "input input--file"
            else:
                widget.attrs["class"] = "input"


class LoginForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "autofocus": True})
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"


class RegisterForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class UserForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["email"].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("home_country",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class ReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ProblemReport
        fields = ("title", "category", "description", "location", "date_of_problem", "image", "share_with_community")
        widgets = {
            "date_of_problem": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 6}),
            "image": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }
        labels = {"title": "Problem title", "description": "What happened?", "location": "Where did it happen?"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["date_of_problem"].widget.attrs["max"] = timezone.localdate().isoformat()
        self.fields["image"].help_text = "JPEG, PNG, or WebP, up to 5 MB."
        self.fields["category"].choices = [("", "Choose a category")] + list(ProblemReport.CATEGORY_CHOICES)

    def clean_date_of_problem(self):
        value = self.cleaned_data["date_of_problem"]
        if value > timezone.localdate():
            raise forms.ValidationError("The date cannot be in the future.")
        return value

    def clean_image(self):
        return validate_image(self.cleaned_data.get("image"))


class ResponseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ReportResponse
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 3})}
        labels = {"body": "Add a reply"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 3:
            raise forms.ValidationError("Write a little more so your reply is useful.")
        return body


# ---------------------------------------------------------------------------
# Password reset (styled to match the site)
# ---------------------------------------------------------------------------

class StyledPasswordResetForm(StyledFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["email"].widget.attrs.update({"autocomplete": "email", "autofocus": True})


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs["autocomplete"] = "new-password"


# ---------------------------------------------------------------------------
# Contact form
# ---------------------------------------------------------------------------

class ContactForm(StyledFormMixin, forms.ModelForm):
    # Honeypot: real visitors never see or fill this field; simple bots do.
    website = forms.CharField(required=False, label="Leave this empty")

    class Meta:
        model = ContactMessage
        fields = ("name", "email", "subject", "message")
        widgets = {"message": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["website"].widget.attrs.update({"tabindex": "-1", "autocomplete": "off"})

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please write at least a short sentence so we can help.")
        return message


# ---------------------------------------------------------------------------
# Admin panel forms
# ---------------------------------------------------------------------------

class AdminLoginForm(LoginForm):
    """Same as the public login, but only staff accounts may sign in to the panel."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError("This area is for site administrators only.", code="not_staff")


class PanelUserForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active", "is_staff")
        labels = {"is_active": "Account is active", "is_staff": "Administrator (can use this panel)"}

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["email"].required = True
        # Only superusers may grant or remove administrator access, and nobody may lock themselves out.
        if actor is None or not actor.is_superuser:
            del self.fields["is_staff"]
        if actor is not None and self.instance.pk == actor.pk:
            for name in ("is_active", "is_staff"):
                if name in self.fields:
                    self.fields[name].disabled = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email


class DestinationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Destination
        fields = ("name", "slug", "place", "category", "blurb", "description", "travel_tip", "image", "featured")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "image": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["image"].help_text = "JPEG, PNG, or WebP, up to 5 MB. Leave empty to use the illustrated scene."

    def clean_image(self):
        return validate_image(self.cleaned_data.get("image"))


class ProblemForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Problem
        fields = ("title", "slug", "icon", "blurb", "overview", "steps", "contacts", "keep_as_proof",
                  "prevention", "order")
        widgets = {
            "overview": forms.Textarea(attrs={"rows": 4}),
            "steps": forms.Textarea(attrs={"rows": 6}),
            "contacts": forms.Textarea(attrs={"rows": 4}),
            "keep_as_proof": forms.Textarea(attrs={"rows": 4}),
            "prevention": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class PanelReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ProblemReport
        fields = ("status", "staff_note")
        widgets = {"staff_note": forms.Textarea(attrs={"rows": 5})}
        labels = {"staff_note": "Update shown to the traveler"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

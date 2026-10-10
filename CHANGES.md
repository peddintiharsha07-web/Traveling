# Changes in this update

> **Testing status:** this update was written in an environment without network access, so Django could not be
> installed and **none of the code or tests have been executed**. Python syntax, template tag balance and URL names
> were checked statically only. Run `python manage.py makemigrations core && python manage.py migrate &&
> python manage.py test` first and fix anything that fails before relying on it.

## New files
- `core/panel_views.py`, `core/panel_urls.py`: the staff admin panel (mounted at `/panel/`).
- `core/notify.py`, `core/signals.py`, `core/context.py`: notifications, activity log helpers, login logging, unread badge.
- `templates/panel/*`: panel layout, login, dashboard, forms, lists, report and message pages.
- `templates/partials/pager.html`: shared pagination control.
- `core/templates/core/`: `contact.html`, `search.html`, `notifications.html`, four `password_reset_*.html`, `emails/*`.

## Changed files
- `core/models.py`: new `ContactMessage`, `Notification`, `ActivityLog`; safe image file names (random name, image
  extensions only) for destinations and reports; report edit/delete permission helpers.
- `core/forms.py`: shared image validation, contact form with honeypot, panel forms, styled password reset forms.
- `core/views.py`: pagination, report edit and delete, notifications, contact, global search, community search and
  filter, dashboard status filter, activity logging, correct content type for report images.
- `core/urls.py`, `config/urls.py`: new routes, password reset, `/panel/`.
- `config/settings.py`: email settings, secret-key guard when `DEBUG=False`, HTTPS switch (`DJANGO_HTTPS`), cookie and
  header hardening, new context processor.
- `core/admin.py`: new models registered in Django admin.
- Templates: pager on destinations, community and dashboard; filters; owner actions on reports; navbar and footer links;
  "Forgot your password?" on login.
- `static/css/main.css`, `static/js/main.js`: panel layout, tables, charts, toolbar, danger buttons; confirm dialogs
  for destructive actions.
- `core/tests.py`: 56 new tests, 74 in total (the 18 existing tests are kept unchanged).
- `README.md`, `.env.example`: updated.

## Not changed
Existing models, seed data, Find Help map, error pages and design tokens are untouched. No new dependencies.

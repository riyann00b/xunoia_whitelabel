# Applied at import time: hooks.py is reliably imported exactly once per
# process (web, background worker, scheduler, console) before any request
# is handled, which is what a process-wide monkeypatch needs.
# SOURCE: apps/erpnext/erpnext/accounts/report/financial_statements.py
# calls pypika's QueryBuilder.force_index(), which always emits MySQL's
# `FORCE INDEX (...)` syntax -- a hard SyntaxError on PostgreSQL sites.
# See xunoia_whitelabel/pg_compat.py for the full explanation.
from xunoia_whitelabel import pg_compat as _pg_compat

_pg_compat.apply()

app_name = "xunoia_whitelabel"
app_title = "XunoiaERP"
app_publisher = "Xunoia Technologies Private Limited"
app_description = "Customer-facing white-label branding for the Frappe/ERPNext desk, website, and documents."
app_email = "engineering@xunoia.com"
app_license = "Proprietary"
app_logo_url = "/assets/xunoia_whitelabel/images/logo.png"
app_color = "#2563eb"
app_home = "/desk"

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": app_title,
		"route": app_home,
	},
]

# App identity used by Frappe's own app-switcher / installed-apps list / about dialog
# version table (frappe.utils.change_log.get_versions() reads app_title from hooks).
# SOURCE: frappe/frappe/boot.py -> get_bootinfo() -> bootinfo.versions = get_versions()
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Assets injected into the Desk (/app) page <head>/<body>.
# SOURCE: hooks.md / docs.frappe.io "Javascript / CSS Assets" reference.
# Loaded AFTER frappe's and erpnext's own bundles (apps load in install order,
# xunoia_whitelabel is installed last), so any `frappe.*` reassignment here
# safely overrides the core definition already on the page.
# ---------------------------------------------------------------------------
app_include_js = "/assets/xunoia_whitelabel/js/xunoia_whitelabel.js"
app_include_css = "/assets/xunoia_whitelabel/css/xunoia_whitelabel.css"

# Same idea for guest-facing website/portal pages (login, /me, web forms).
web_include_css = "/assets/xunoia_whitelabel/css/xunoia_whitelabel.css"

# ---------------------------------------------------------------------------
# Boot data.
#
# SOURCE (verified against the `develop` branch, Sept 2026):
#   frappe/frappe/boot.py      -> get_bootinfo() sets bootinfo.navbar_settings
#                                  via get_navbar_settings() BEFORE returning.
#   frappe/frappe/sessions.py  -> sessions.get() calls
#                                  `bootinfo = get_bootinfo()`
#                                  then, further down:
#                                  `for hook in frappe.get_hooks("extend_bootinfo"):
#                                       frappe.get_attr(hook)(bootinfo=bootinfo)`
#
# So `extend_bootinfo` always fires AFTER bootinfo.navbar_settings (and
# .help_dropdown) already exist. This is the fix for the timing problem
# described in the brief: `extend_bootinfo` is NOT too early — it is the
# correct, current, documented hook (docs.frappe.io still shows it as
# `extend_bootinfo = "app.boot.boot_session"`). If an earlier attempt saw an
# empty navbar_settings, the likely cause is one of:
#   - the hook fired on a *website/Guest* boot payload (portal pages build a
#     stripped-down boot object that never calls get_navbar_settings() at
#     all, since Help/navbar-settings are a Desk-only concept), or
#   - the function was wired to a different/misspelled hooks.py key.
# Confirm locally with the browser-console check in the Verification section.
# ---------------------------------------------------------------------------
extend_bootinfo = "xunoia_whitelabel.boot.boot_session"

# ---------------------------------------------------------------------------
# after_migrate: idempotent, non-destructive config seeding.
# Fires on every `bench migrate` / `pilot site migrate`. install.py guards
# every write so re-running it is always a no-op once state matches.
# ---------------------------------------------------------------------------
after_migrate = "xunoia_whitelabel.install.after_migrate"
after_install = "xunoia_whitelabel.install.after_install"

# ---------------------------------------------------------------------------
# Website / portal context overrides.
# SOURCE: hooks.md "Website Context" reference (website_context dict +
# update_website_context callable).
# ---------------------------------------------------------------------------
website_context = {
	"favicon": "/assets/xunoia_whitelabel/images/favicon.png",
	"splash_image": "/assets/xunoia_whitelabel/images/logo.png",
}
update_website_context = "xunoia_whitelabel.www.website_context.update_context"

# ---------------------------------------------------------------------------
# Jinja template overrides.
# MECHANISM: Frappe's Jinja loader is a ChoiceLoader over every installed
# app's `templates/` folder. A template placed at the same relative path in
# a later-installed app wins over the framework's own copy of that path.
# xunoia_whitelabel installs after frappe/erpnext, so these two paths
# transparently replace the stock ones with no core edits.
# The active v16 loader resolves these exact paths from this app:
# templates/emails/email_footer.html
# templates/includes/footer/footer_powered.html

doctype_js = {}

fixtures = [
	{
		"doctype": "Letter Head",
		"filters": [["name", "=", "Xunoia Letter Head"]],
	},
]

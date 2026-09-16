app_name = "xunoia_whitelabel"
app_title = "Xunoia"
app_publisher = "Xunoia Technologies Private Limited"
app_description = "Customer-facing white-label branding for the Frappe/ERPNext desk, website, and documents."
app_email = "engineering@xunoia.com"
app_license = "Proprietary"

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
# EVIDENCE: ENGINEERING RECOMMENDATION (documented Frappe behavior) —
# confirm the exact precedence order for your installed-app order locally
# (see Verification section) before relying on it for anything security
# sensitive.
# ---------------------------------------------------------------------------
# templates/emails/standard.html      -> overrides the default system-email
#                                         wrapper (drops "Powered by Frappe").
#                                         Block name used (`footer_brand`) is
#                                         a best-known name — confirm it
#                                         against your installed version (see
#                                         Verification: source-search).
#
# The website footer's "Powered by ERPNext/Frappe" line did not get a
# template override in this pass because its exact include path was not
# independently re-verified against current source within this session's
# research budget (see Residual Branding / Evidence Standard in the
# accompanying report). Until confirmed, public/css/xunoia_whitelabel.css
# hides it visually as a tier-7 fallback.

doctype_js = {
	# Placeholder for future per-doctype JS overrides (e.g. Print Format
	# preview branding). Intentionally empty for v0.1.
}

fixtures = [
	{
		"doctype": "Letter Head",
		"filters": [["name", "=", "Xunoia Letter Head"]],
	},
]

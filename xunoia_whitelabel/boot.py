# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary
"""
extend_bootinfo handler.

Runs inside frappe.sessions.get(), immediately after frappe.boot.get_bootinfo()
has already populated `bootinfo.navbar_settings` (see hooks.py for the source
citations that establish this ordering).

Nothing here writes to the database. It only edits the in-memory `bootinfo`
dict before it is serialized to the browser as `frappe.boot`. That makes this
handler trivially idempotent (it runs fresh, from the real DB state, on every
single page boot) and completely unaffected by `bench migrate`, asset
rebuilds, or core upgrades — there is no state to drift out of sync.

Per the Frappe hooks reference: "NEVER put secrets/API keys in bootinfo — it
is sent to the browser. NEVER run heavy queries in bootinfo — it runs on
EVERY page load." Accordingly, brand info is read through
frappe.get_cached_doc (single Redis-cached fetch), and nothing else here
touches the database.
"""

import frappe

# Stock Navbar Settings > Help Dropdown items that should never reach a
# Xunoia-branded desk, regardless of what a future core migration re-adds.
HIDDEN_HELP_ITEMS = {"Frappe Support"}

# Stock Help Dropdown items whose destination should point at Xunoia's own
# properties instead of frappe.io. Matched by item_label; only the fields
# listed are overwritten, everything else on the row (icon, idx, condition)
# is left untouched.
RELABELLED_HELP_ITEMS = {
	"About": {"item_label": "About Xunoia"},
	"Documentation": {
		"item_label": "Xunoia Documentation",
		"route": None,  # cleared below in favour of external_link
	},
}


def boot_session(bootinfo):
	"""Registered as `extend_bootinfo` in hooks.py."""
	_strip_and_relabel_help_dropdown(bootinfo)
	_inject_xunoia_branding(bootinfo)


def _strip_and_relabel_help_dropdown(bootinfo):
	navbar_settings = bootinfo.get("navbar_settings")
	if not navbar_settings:
		# Defensive: on a Guest/website boot payload this key may not exist
		# at all (navbar_settings is a Desk-only concept). Nothing to do.
		return

	help_dropdown = navbar_settings.get("help_dropdown") or []
	if not help_dropdown:
		return

	kept_items = []
	changed = False

	for item in help_dropdown:
		label = item.get("item_label")

		if label in HIDDEN_HELP_ITEMS:
			changed = True
			continue  # drop this row from the boot payload entirely

		override = RELABELLED_HELP_ITEMS.get(label)
		if override:
			item.update({k: v for k, v in override.items() if v is not None})
			changed = True

		kept_items.append(item)

	if changed:
		navbar_settings["help_dropdown"] = kept_items


def _inject_xunoia_branding(bootinfo):
	"""Expose the single source of truth for brand strings to client JS.

	Namespaced as `frappe.boot.xunoia.branding` to match the shape already
	consumed by the working show_about() override (public/js/xunoia_whitelabel.js)
	referenced in the brief — this keeps that override unchanged and adds a
	*source*, not a second, incompatible shape.
	"""
	settings = frappe.get_cached_doc("Xunoia Brand Settings")
	bootinfo.xunoia = {
		"branding": {
			"product_name": settings.product_name or "Xunoia",
			"company_name": settings.company_name or "Xunoia",
			"logo": settings.logo,
			"website_url": settings.website_url,
			"documentation_url": settings.documentation_url,
			"support_url": settings.support_url,
		}
	}

# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary

"""
extend_bootinfo handler.

Runs inside frappe.sessions.get(), after frappe.boot.get_bootinfo()
has populated bootinfo.navbar_settings.

This handler only modifies the in-memory boot payload. It does not write
anything to the database.

Brand information is read through frappe.get_cached_doc() so the boot
request uses the cached Xunoia Brand Settings document.
"""

import frappe


# Stock Navbar Settings items (Help Dropdown and Settings Dropdown) that
# should never reach an Xunoia-branded Desk.
HIDDEN_HELP_ITEMS = {
	"Frappe Support",
	"User Forum",
	"Frappe School",
	"Report an Issue",
}


# Stock Help Dropdown items whose visible label/destination should be
# changed for Xunoia.
RELABELLED_HELP_ITEMS = {
	"About": {
		"item_label": "About Xunoia",
	},
	"Documentation": {"item_label": "Xunoia Documentation"},
}


def boot_session(bootinfo):
	"""Registered as `extend_bootinfo` in hooks.py."""
	_strip_and_relabel_navbar_dropdown(bootinfo, "help_dropdown")
	_strip_and_relabel_navbar_dropdown(bootinfo, "settings_dropdown")
	_inject_xunoia_branding(bootinfo)
	_rebrand_app_data(bootinfo)


def _strip_and_relabel_navbar_dropdown(bootinfo, table_fieldname):
	"""
	Remove/relabel entries in a Navbar Settings dropdown table
	(`help_dropdown` or `settings_dropdown`) in the in-memory boot payload.

	Navbar Settings is a Frappe Document object, not a plain dictionary.
	Therefore `.get()` is used for reading and `.set()` is used for writing.
	"""
	navbar_settings = bootinfo.get("navbar_settings")

	if not navbar_settings:
		# Guest/website boot payloads may not contain navbar_settings.
		return

	items = navbar_settings.get(table_fieldname) or []

	if not items:
		return

	kept_items = []
	changed = False

	for item in items:
		label = item.get("item_label")

		# Remove stock Frappe Support.
		if label in HIDDEN_HELP_ITEMS:
			changed = True
			continue

		# Relabel selected stock entries.
		override = RELABELLED_HELP_ITEMS.get(label)

		if override:
			for key, value in override.items():
				if value is not None:
					item.set(key, value)

			changed = True

		kept_items.append(item)

	if changed:
		navbar_settings.set(table_fieldname, kept_items)


def _rebrand_app_data(bootinfo):
	"""Replace framework/app labels and logos in Desk app metadata."""
	branding = _get_branding()
	for app in bootinfo.get("app_data") or []:
		if app.get("app_name") in {"frappe", "erpnext", "xunoia_whitelabel"}:
			app["app_title"] = branding["product_name"]
			app["app_logo_url"] = branding["logo"]


def _inject_xunoia_branding(bootinfo):
	"""
	Expose the centralized Xunoia branding configuration to Desk JavaScript.

	Available to the browser as:

	    frappe.boot.xunoia.branding
	    frappe.boot.xunoia.hidden_menu_labels
	"""
	bootinfo.xunoia = {
		"branding": _get_branding(),
		# Frappe v16's avatar/profile menu (frappe/desk/page/desktop/desktop.js
		# setup_avatar()) builds its items as a hardcoded JS array and never
		# touches bootinfo.navbar_settings, so it can't be filtered here in
		# Python. Exposing this set lets xunoia_whitelabel.js filter that menu
		# too, off the same source of truth instead of a second hardcoded list.
		"hidden_menu_labels": sorted(HIDDEN_HELP_ITEMS),
	}


def _get_branding():
	settings = frappe.get_cached_doc("Xunoia Brand Settings")
	return {
		"product_name": settings.product_name or "XunoiaERP",
		"company_name": settings.company_name or "Xunoia",
		"logo": settings.logo or "/assets/xunoia_whitelabel/images/logo.png",
		"favicon": settings.favicon or "/assets/xunoia_whitelabel/images/favicon.png",
		"website_url": settings.website_url or "https://xunoia.com",
		"documentation_url": settings.documentation_url or "https://docs.xunoia.com",
		"support_url": settings.support_url or "https://support.xunoia.com",
	}

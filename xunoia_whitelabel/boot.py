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


# Stock Navbar Settings > Help Dropdown items that should never reach
# an Xunoia-branded Desk.
HIDDEN_HELP_ITEMS = {
	"Frappe Support",
}


# Stock Help Dropdown items whose visible label/destination should be
# changed for Xunoia.
RELABELLED_HELP_ITEMS = {
	"About": {
		"item_label": "About Xunoia",
	},
	"Documentation": {
		"item_label": "Xunoia Documentation",
		"route": None,
	},
}


def boot_session(bootinfo):
	"""Registered as `extend_bootinfo` in hooks.py."""
	_strip_and_relabel_help_dropdown(bootinfo)
	_inject_xunoia_branding(bootinfo)


def _strip_and_relabel_help_dropdown(bootinfo):
	"""
	Remove/relabel Help dropdown entries in the in-memory boot payload.

	Navbar Settings is a Frappe Document object, not a plain dictionary.
	Therefore `.get()` is used for reading and `.set()` is used for writing.
	"""
	navbar_settings = bootinfo.get("navbar_settings")

	if not navbar_settings:
		# Guest/website boot payloads may not contain navbar_settings.
		return

	help_dropdown = navbar_settings.get("help_dropdown") or []

	if not help_dropdown:
		return

	kept_items = []
	changed = False

	for item in help_dropdown:
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
		navbar_settings.set("help_dropdown", kept_items)


def _inject_xunoia_branding(bootinfo):
	"""
	Expose the centralized Xunoia branding configuration to Desk JavaScript.

	Available to the browser as:

	    frappe.boot.xunoia.branding
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

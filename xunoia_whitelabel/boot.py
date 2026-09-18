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


# Stock items that should never reach an Xunoia-branded Desk: Navbar
# Settings rows (Help Dropdown / Settings Dropdown, matched by item_label)
# and hardcoded avatar/profile-menu entries (matched by label via
# hidden_menu_labels below).
HIDDEN_HELP_ITEMS = {
	"Frappe Support",
	"User Forum",
	"Frappe School",
	"Report an Issue",
	# Not a Navbar Settings row -- billing.bundle.js pushes this into the
	# same avatar/profile menu (gated by frappe.boot.is_fc_site, normally
	# inert unless fc_communication_secret is ever set). Filtered by the
	# same frappe.ui.create_menu() label check as the rest of this set.
	"Manage Billing",
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
	_hide_cloud_settings(bootinfo)
	_inject_xunoia_branding(bootinfo)
	_rebrand_app_data(bootinfo)


def _hide_cloud_settings(bootinfo):
	"""
	Force-disable the Cloud Settings desktop button for every session on
	this Xunoia-branded Desk.

	SOURCE: frappe/boot.py get_bootinfo() sets
	    bootinfo.cloud_settings = get_cloud_settings_boot_context()
	(frappe/integrations/frappe_providers/cloud_settings.py), which returns
	{"enabled": True, ...} whenever site_config has pilot_endpoint +
	pilot_auth_token AND the user has the System Manager role. Both are set
	on this bench for real pilot backend functionality, so the credentials
	themselves must stay -- clearing them would break pilot, not just this
	button.

	frappe/desk/page/desktop/desktop.js setup_cloud_settings() already
	reads exactly this `enabled` flag before unhiding `.desktop-cloud-settings`
	and fetching pilot's embed bundle. Forcing it false here in the
	in-memory boot payload (same technique as
	_strip_and_relabel_navbar_dropdown above) is the exact kill switch the
	stock client code was built to respect: the button never unhides and
	the embed bundle is never fetched. No change to frappe.conf; no effect
	on any whitelisted RPC that re-checks is_cloud_settings_enabled()
	server-side.
	"""
	if bootinfo.get("cloud_settings"):
		bootinfo.cloud_settings = {"enabled": False}


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
		app_name = app.get("app_name")
		if app_name in {"frappe", "erpnext", "xunoia_whitelabel"}:
			app["app_title"] = branding["product_name"]
			app["app_logo_url"] = branding["logo"]
		elif app_name == "hrms":
			# Frappe HR is sold as its own named module. Only display fields
			# change: the client matches apps on app_name, never app_title.
			app["app_title"] = branding["hr_product_name"]
			app["app_logo_url"] = branding["logo"]


def _inject_xunoia_branding(bootinfo):
	"""
	Expose the centralized Xunoia branding configuration to Desk JavaScript.

	Available to the browser as:

	    frappe.boot.xunoia.branding
	    frappe.boot.xunoia.hidden_menu_labels
	    frappe.boot.xunoia.disable_desk_right_click
	"""
	branding = _get_branding()
	bootinfo.xunoia = {
		"branding": branding,
		"disable_desk_right_click": branding["disable_desk_right_click"],
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
		"hr_product_name": settings.hr_product_name or "XunoiaHR",
		"company_name": settings.company_name or "Xunoia",
		"logo": settings.logo or "/assets/xunoia_whitelabel/images/logo.png",
		"favicon": settings.favicon or "/assets/xunoia_whitelabel/images/favicon.png",
		"website_url": settings.website_url or "https://xunoia.com",
		"documentation_url": settings.documentation_url or "https://docs.xunoia.com",
		"support_url": settings.support_url or "https://support.xunoia.com",
		"disable_desk_right_click": bool(settings.get("disable_desk_right_click", 1)),
	}

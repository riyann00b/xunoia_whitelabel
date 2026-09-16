# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary
"""
after_install / after_migrate.

Design constraints from the spec, and how each is met:

  - idempotent      -> every write below is preceded by a read; we only ever
                        write when the current DB value differs from the
                        target value, so a second/third/Nth run is a no-op.
  - site-safe       -> only Xunoia-owned rows/doctypes are touched. Existing
                        Navbar Settings rows this app did not create (e.g. an
                        admin's own custom navbar links) are left alone.
  - upgrade-conscious -> nothing here depends on a specific frappe/erpnext
                        version beyond the Navbar Settings / Navbar Item
                        doctypes existing (stable since v13).
  - minimally invasive -> no apps/frappe or apps/erpnext files are touched;
                        every write targets a doc this app owns
                        (Xunoia Brand Settings) or a single named child row
                        (the "Xunoia Support"/"Xunoia Documentation" navbar
                        items), never a blanket table replace.

Note: removing the stock "Frappe Support" item from what the BROWSER sees is
already handled non-destructively, on every boot, by boot.py's
extend_bootinfo handler — nothing below needs to touch that row at all. What
IS handled here is adding Xunoia's own navbar entries, which (unlike a
removal) genuinely needs to be persisted, because they must survive being
listed in Navbar Settings if an admin opens that doctype in the desk.
"""

import frappe


def after_install():
	_ensure_brand_settings()
	_ensure_xunoia_navbar_items()


def after_migrate():
	# Same idempotent operations as after_install. Safe to run on every
	# `bench migrate` / `pilot site migrate` — see module docstring.
	_ensure_brand_settings()
	_ensure_xunoia_navbar_items()


def _ensure_brand_settings():
	"""Create the Xunoia Brand Settings singleton with sane defaults exactly
	once. Never overwrites fields an operator has since edited — this only
	fills in blanks, it never clobbers.
	"""
	settings = frappe.get_single("Xunoia Brand Settings")

	defaults = {
		"product_name": "Xunoia",
		"company_name": "Xunoia",
		"website_url": "https://xunoia.com",
		"documentation_url": "https://docs.xunoia.com",
		"support_url": "https://support.xunoia.com",
	}

	dirty = False
	for fieldname, default_value in defaults.items():
		if not settings.get(fieldname):
			settings.set(fieldname, default_value)
			dirty = True

	if dirty:
		settings.flags.ignore_permissions = True
		settings.save()


def _ensure_xunoia_navbar_items():
	"""Add Xunoia's own Help-dropdown rows if they are not already present.

	Matched by item_label so this is safe to re-run: if the row already
	exists (because a previous run added it, or an admin manually added an
	identically-labelled row) nothing is written.
	"""
	navbar_settings = frappe.get_single("Navbar Settings")
	existing_labels = {row.item_label for row in navbar_settings.help_dropdown}

	brand = frappe.get_single("Xunoia Brand Settings")
	wanted_rows = [
		{
			"item_label": "Xunoia Documentation",
			"item_type": "Route",
			"route": brand.documentation_url or "https://docs.xunoia.com",
			"is_standard": 0,
		},
		{
			"item_label": "Xunoia Support",
			"item_type": "Route",
			"route": brand.support_url or "https://support.xunoia.com",
			"is_standard": 0,
		},
	]

	rows_to_add = [row for row in wanted_rows if row["item_label"] not in existing_labels]
	if not rows_to_add:
		return  # already in the desired state — idempotent no-op

	for row in rows_to_add:
		navbar_settings.append("help_dropdown", row)

	navbar_settings.flags.ignore_permissions = True
	navbar_settings.save()

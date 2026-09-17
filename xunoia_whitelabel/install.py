# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary
"""
after_install / after_migrate.

Design constraints from the spec, and how each is met:

  - idempotent      -> every write below is preceded by a read; we only ever
                        write when the current DB value differs from the
                        target value, so a second/third/Nth run is a no-op.
  - site-safe       -> only stock framework/ERPNext navbar rows and this app's
                        own settings are touched. Administrator-created
                        custom navbar links are left alone.
  - upgrade-conscious -> nothing here depends on a specific frappe/erpnext
                        version beyond the Navbar Settings / Navbar Item
                        doctypes existing (stable since v13).
  - minimally invasive -> no apps/frappe or apps/erpnext files are touched;
                        every write targets a doc this app owns
                        (Xunoia Brand Settings) or known stock child rows
                        (plus the Xunoia Documentation/Support rows), never a
                        blanket table replacement.

The boot handler also removes the same stock rows from the in-memory payload.
The persisted cleanup below is needed so migrations and administrators opening
Navbar Settings do not recreate the customer-facing framework links.
"""

import frappe


def after_install():
	_ensure_brand_settings()
	_ensure_xunoia_navbar_items()
	_rebrand_erpnext_workspace_labels()


def after_migrate():
	# Same idempotent operations as after_install. Safe to run on every
	# `bench migrate` / `pilot site migrate` — see module docstring.
	_ensure_brand_settings()
	_ensure_xunoia_navbar_items()
	_rebrand_erpnext_workspace_labels()


def _ensure_brand_settings():
	"""Create the Xunoia Brand Settings singleton with sane defaults exactly
	once. Never overwrites fields an operator has since edited — this only
	fills in blanks, it never clobbers.
	"""
	settings = frappe.get_single("Xunoia Brand Settings")

	defaults = {
		"product_name": "XunoiaERP",
		"company_name": "Xunoia",
		"logo": "/assets/xunoia_whitelabel/images/logo.png",
		"favicon": "/assets/xunoia_whitelabel/images/favicon.png",
		"website_url": "https://xunoia.com",
		"documentation_url": "https://docs.xunoia.com",
		"support_url": "https://support.xunoia.com",
	}

	dirty = False
	for fieldname, default_value in defaults.items():
		current_value = settings.get(fieldname)
		if not current_value or (
			fieldname == "product_name"
			and current_value in {"Xunoia", "Frappe", "Frappe Framework", "ERPNext"}
		):
			settings.set(fieldname, default_value)
			dirty = True

	if dirty:
		settings.flags.ignore_permissions = True
		settings.save()

	_set_customer_facing_app_names(settings)


def _set_customer_facing_app_names(settings):
	"""Set stock/default identity values without clobbering custom names."""
	product_name = settings.product_name or "XunoiaERP"
	for doctype in ("Website Settings", "System Settings"):
		current = frappe.get_single_value(doctype, "app_name")
		if not current or current in {"Xunoia", "Frappe", "Frappe Framework", "ERPNext"}:
			frappe.db.set_single_value(doctype, "app_name", product_name)

	navbar_settings = frappe.get_single("Navbar Settings")
	if not navbar_settings.app_logo or navbar_settings.app_logo in {
		"/assets/frappe/images/frappe-framework-logo.svg",
		"/assets/erpnext/images/erpnext-logo.svg",
	}:
		navbar_settings.app_logo = settings.logo
		navbar_settings.flags.ignore_permissions = True
		navbar_settings.save()


def _ensure_xunoia_navbar_items():
	"""Add Xunoia's own Help-dropdown rows if they are not already present.

	Matched by item_label so this is safe to re-run: if the row already
	exists (because a previous run added it, or an admin manually added an
	identically-labelled row) nothing is written.
	"""
	navbar_settings = frappe.get_single("Navbar Settings")
	stock_labels = {
		"Frappe Support",
		"User Forum",
		"Frappe School",
		"Report an Issue",
	}
	stock_routes = {
		"https://frappe.io/support",
		"https://docs.erpnext.com/",
		"https://discuss.frappe.io",
		"https://frappe.io/school?utm_source=in_app",
		"https://github.com/frappe/erpnext/issues",
	}
	kept_rows = [
		row
		for row in navbar_settings.help_dropdown
		if row.item_label not in stock_labels and row.route not in stock_routes
	]
	removed_rows = len(kept_rows) != len(navbar_settings.help_dropdown)
	if removed_rows:
		navbar_settings.set("help_dropdown", kept_rows)

	existing_labels = {row.item_label for row in kept_rows}

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
	for row in rows_to_add:
		navbar_settings.append("help_dropdown", row)

	if rows_to_add or removed_rows:
		navbar_settings.flags.ignore_permissions = True
		navbar_settings.save()


def _rebrand_erpnext_workspace_labels():
	"""
	Relabel stock ERPNext-branded Workspace/sidebar entries so "ERPNext
	Settings" (the last tile in the Workspaces list) reads as
	"<product_name> Settings" instead.

	v16 ships that one visible tile as three separate records that must
	all agree:
	  - Desktop Icon "ERPNext Settings"      -> the tile itself, shown in
	    the Workspaces list (erpnext/desktop_icon/erpnext_settings.json)
	  - Workspace Sidebar "ERPNext Settings" -> the left-sidebar tree shown
	    once that tile is opened (erpnext/workspace_sidebar/erpnext_settings.json)
	  - Workspace "ERPNext Settings"         -> the underlying workspace
	    page (erpnext/setup/workspace/erpnext_settings/erpnext_settings.json)
	Plus the top-level "ERPNext" Desktop Icon (erpnext/desktop_icon/erpnext.json),
	hidden by default so it isn't in the list today, but relabelled too in
	case it's ever unhidden.

	Docnames are left untouched -- only label/title display fields change --
	so the Desktop Icon's own `link_to: "ERPNext Settings"` (a name
	reference to the Workspace Sidebar record) keeps resolving correctly.
	Matched against the known stock label so an administrator's own rename
	is never clobbered; same idempotent, read-before-write approach as the
	rest of this module.
	"""
	brand = frappe.get_single("Xunoia Brand Settings")
	product_name = brand.product_name or "XunoiaERP"

	# (doctype, docname, fieldnames, target label, stock labels safe to overwrite)
	targets = [
		("Desktop Icon", "ERPNext Settings", ("label",), f"{product_name} Settings", {"ERPNext Settings"}),
		("Workspace Sidebar", "ERPNext Settings", ("title",), f"{product_name} Settings", {"ERPNext Settings"}),
		("Workspace", "ERPNext Settings", ("label", "title"), f"{product_name} Settings", {"ERPNext Settings"}),
		("Desktop Icon", "ERPNext", ("label",), product_name, {"ERPNext"}),
	]

	for doctype, docname, fieldnames, target, stock_labels in targets:
		if not frappe.db.exists(doctype, docname):
			continue
		for fieldname in fieldnames:
			current = frappe.db.get_value(doctype, docname, fieldname)
			if current in stock_labels and current != target:
				frappe.db.set_value(doctype, docname, fieldname, target)

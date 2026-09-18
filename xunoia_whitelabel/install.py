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
	_hide_xunoia_self_icon()
	_rebrand_hrms_desktop_icon()


def after_migrate():
	# Same idempotent operations as after_install. Safe to run on every
	# `bench migrate` / `pilot site migrate` — see module docstring.
	_ensure_brand_settings()
	_ensure_xunoia_navbar_items()
	_rebrand_erpnext_workspace_labels()
	_hide_xunoia_self_icon()
	_rebrand_hrms_desktop_icon()


def _ensure_brand_settings():
	"""Create the Xunoia Brand Settings singleton with sane defaults exactly
	once. Never overwrites fields an operator has since edited — this only
	fills in blanks, it never clobbers.
	"""
	settings = frappe.get_single("Xunoia Brand Settings")

	defaults = {
		"product_name": "XunoiaERP",
		"hr_product_name": "XunoiaHR",
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

	Docnames are left untouched -- only label/title display fields change --
	so the Desktop Icon's own `link_to: "ERPNext Settings"` (a name
	reference to the Workspace Sidebar record) keeps resolving correctly.
	Matched against the known stock label so an administrator's own rename
	is never clobbered; writes go through _set_unique_label_if_stock(),
	which also guards the unique-constraint collision documented there.

	There is no fourth target relabelling the hidden top-level "ERPNext"
	Desktop Icon to the bare product_name: Frappe's after_app_install hook
	(frappe.utils.install.auto_generate_icons_and_sidebar) already creates
	a Desktop Icon for this app itself, labelled from app_title ("XunoiaERP"
	per hooks.py) -- so that value is permanently owned by this app's own
	self-icon on any correctly-installed site, and attempting it here always
	collides (confirmed: this is what broke production migrate.py, before
	the skip-on-collision guard above existed).
	"""
	brand = frappe.get_single("Xunoia Brand Settings")
	product_name = brand.product_name or "XunoiaERP"
	target = f"{product_name} Settings"
	stock_labels = {"ERPNext Settings"}

	# (doctype, docname, fieldnames to relabel)
	targets = [
		("Desktop Icon", "ERPNext Settings", ("label",)),
		("Workspace Sidebar", "ERPNext Settings", ("title",)),
		("Workspace", "ERPNext Settings", ("label", "title")),
	]

	for doctype, docname, fieldnames in targets:
		for fieldname in fieldnames:
			_set_unique_label_if_stock(doctype, docname, fieldname, target, stock_labels)


def _set_unique_label_if_stock(doctype, docname, fieldname, target, stock_labels):
	"""
	Write `target` to `fieldname` on `doctype`/`docname`, but only when:
	  - the record exists,
	  - its current value is a known stock default (never clobbers an
	    administrator's own rename), and
	  - no *other* row already owns `target`.

	That last check matters because Desktop Icon.label, Workspace.label and
	Workspace Sidebar.title are each `autoname: field:<that field>` with a
	DB-level unique constraint -- writing a value already claimed by a
	different row raises IntegrityError and, since `after_migrate` hooks run
	inside migrate.py's @atomic post_schema_updates(), aborts and rolls back
	the *entire* migrate data-sync phase for every app, not just this write
	(confirmed: this is exactly what broke a production `bench migrate`
	before this guard existed). Skips with a printed note instead of
	raising if that happens.
	"""
	if not frappe.db.exists(doctype, docname):
		return
	current = frappe.db.get_value(doctype, docname, fieldname)
	if current not in stock_labels or current == target:
		return
	if frappe.db.exists(doctype, {fieldname: target}):
		print(
			f"xunoia_whitelabel: skipped setting {doctype} {docname}.{fieldname} "
			f"to {target!r} -- already in use by another {doctype} record."
		)
		return
	frappe.db.set_value(doctype, docname, fieldname, target)


def _hide_xunoia_self_icon():
	"""
	Hide the Desktop Icon Frappe auto-generates for this app itself.

	frappe.utils.install.auto_generate_icons_and_sidebar() -- wired as
	after_app_install, and also re-run once, for any site that hadn't
	already had it, by the core patch
	frappe.patches.v16_0.auto_generate_desktop_icon_and_sidebar -- creates a
	Desktop Icon for every installed app that doesn't have one yet, reading
	the `add_to_apps_screen` hook: label = app_title ("XunoiaERP"),
	link_type "External", link = app_home ("/desk"). That's the right
	behaviour for a framework with several genuinely separate installed
	apps to switch between, but Xunoia is the whole product, not one tile
	among several -- a self-referential "XunoiaERP" icon that just reloads
	the page it's already on undermines the whitelabel and does nothing
	useful for an end user.

	Matched by the `app` field (stable regardless of label/product_name),
	and only hidden, never deleted -- consistent with how the stock
	"ERPNext" Desktop Icon already ships hidden rather than removed, and
	keeps add_to_apps_screen itself intact for whatever else reads it
	(e.g. the app switcher).
	"""
	icon_name = frappe.db.get_value("Desktop Icon", {"app": "xunoia_whitelabel"}, "name")
	if icon_name and not frappe.db.get_value("Desktop Icon", icon_name, "hidden"):
		frappe.db.set_value("Desktop Icon", icon_name, "hidden", 1)


def _rebrand_hrms_desktop_icon():
	"""
	Relabel the stock "Frappe HR" Desktop Icon -- the HR tile in the
	Workspaces list (hrms/desktop_icon/frappe_hr.json, link: /desk/people)
	-- to hr_product_name ("XunoiaHR" by default).

	Unlike this app's own self-icon (_hide_xunoia_self_icon), this one is a
	real, useful navigation tile, so it's relabelled rather than hidden --
	same treatment as _rebrand_erpnext_workspace_labels, but a distinct
	brand name (hr_product_name, not product_name), since Xunoia sells HR
	as its own named module rather than folding it into the main product
	name.

	Every other stock hrms Desktop Icon (hr_setup, payroll, expenses,
	leaves, shift_&_attendance, performance, tax_&_benefits, tenure,
	recruitment) references this one by docname via `"parent_icon":
	"Frappe HR"` -- since only the label changes here, never the docname,
	those references keep resolving with no further changes needed.

	No-ops entirely if hrms isn't installed on this site (Desktop Icon
	"Frappe HR" won't exist) -- see _set_unique_label_if_stock.
	"""
	brand = frappe.get_single("Xunoia Brand Settings")
	hr_product_name = brand.hr_product_name or "XunoiaHR"
	_set_unique_label_if_stock("Desktop Icon", "Frappe HR", "label", hr_product_name, {"Frappe HR"})

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
from frappe.desk.doctype.desktop_icon.desktop_icon import get_app_desktop_icon

from xunoia_whitelabel.xunoia_whitelabel.doctype.xunoia_brand_settings.xunoia_brand_settings import (
	BRAND_DEFAULTS,
	sync_system_settings,
)


def after_install():
	_ensure_brand_settings()
	_ensure_xunoia_navbar_items()
	rebrand_erpnext_workspace_labels()
	_remove_xunoia_self_icon()
	_remove_frappe_framework_icon()
	_show_crm_icon()
	_restore_hrms_desktop_icon_label()
	_ensure_brand_translations()


def after_migrate():
	# Same idempotent operations as after_install. Safe to run on every
	# `bench migrate` / `pilot site migrate` — see module docstring.
	_ensure_brand_settings()
	_ensure_xunoia_navbar_items()
	rebrand_erpnext_workspace_labels()
	_remove_xunoia_self_icon()
	_remove_frappe_framework_icon()
	_show_crm_icon()
	_restore_hrms_desktop_icon_label()
	_ensure_brand_translations()


def _ensure_brand_settings():
	"""Create the Xunoia Brand Settings singleton with sane defaults exactly
	once. Never overwrites fields an operator has since edited — this only
	fills in blanks, it never clobbers.
	"""
	settings = frappe.get_single("Xunoia Brand Settings")

	# Check fields: 0 is a deliberate operator choice, not a blank, so the
	# `not current_value` test used for the BRAND_DEFAULTS text fields would flip an
	# unchecked toggle back on every migrate. Seed these only when the field
	# has never been stored at all (fresh install, or the field was added by
	# a later app version).
	check_defaults = {
		"disable_desk_right_click": 1,
		"disable_update_notification": 1,
		"disable_product_suggestion": 1,
	}

	dirty = False
	for fieldname, default_value in BRAND_DEFAULTS.items():
		current_value = settings.get(fieldname)
		if not current_value or (
			fieldname == "product_name"
			and current_value in {"Xunoia", "Frappe", "Frappe Framework", "ERPNext"}
		):
			settings.set(fieldname, default_value)
			dirty = True

	stored_fields = _stored_single_fields("Xunoia Brand Settings")
	for fieldname, default_value in check_defaults.items():
		if fieldname not in stored_fields:
			settings.set(fieldname, default_value)
			dirty = True

	if dirty:
		settings.flags.ignore_permissions = True
		settings.save()
	else:
		sync_system_settings(settings)

	_set_customer_facing_app_names(settings)


def _stored_single_fields(doctype):
	"""Fieldnames that have a row in tabSingles for this Single DocType.

	Loading a Single through the ORM casts missing Check fields to 0, which
	is indistinguishable from an explicit 0, so read the raw table instead.
	"""
	singles = frappe.qb.DocType("Singles")
	return set(
		frappe.qb.from_(singles).select(singles.field).where(singles.doctype == doctype).run(pluck=True)
	)


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


def rebrand_erpnext_workspace_labels(previous_product_name=None):
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
	is never clobbered; same idempotent, read-before-write approach as the
	rest of this module.

	CAUTION: Desktop Icon.label, Workspace.label and Workspace Sidebar.title
	are each `autoname: field:<that field>` with a DB-level unique
	constraint -- writing a value already claimed by a different row raises
	IntegrityError and, since `after_migrate` hooks run inside migrate.py's
	@atomic post_schema_updates(), aborts and rolls back the *entire*
	migrate data-sync phase for every app, not just this write. Every write
	below checks for that collision first and skips (never raises) if the
	target is already taken by another row.

	There is no fourth target relabelling the hidden top-level "ERPNext"
	Desktop Icon to the bare product_name: Frappe's after_app_install hook
	(frappe.utils.install.auto_generate_icons_and_sidebar) already creates
	a Desktop Icon for this app itself, labelled from app_title ("XunoiaERP"
	per hooks.py) -- so that value is permanently owned by this app's own
	self-icon on any correctly-installed site, and attempting it here always
	collides (confirmed: this is what broke production migrate.py, before
	the skip-on-collision guard above existed).

	`previous_product_name` is passed by Xunoia Brand Settings.on_update when
	the product is renamed, so "<old> Settings" -- a label this function
	wrote itself -- follows the new name too.
	"""
	brand = frappe.get_single("Xunoia Brand Settings")
	product_name = brand.product_name or BRAND_DEFAULTS["product_name"]
	target = f"{product_name} Settings"
	stock_labels = {"ERPNext Settings"}
	if previous_product_name:
		stock_labels.add(f"{previous_product_name} Settings")

	# (doctype, docname, fieldnames to relabel)
	targets = [
		("Desktop Icon", "ERPNext Settings", ("label",)),
		("Workspace Sidebar", "ERPNext Settings", ("title",)),
		("Workspace", "ERPNext Settings", ("label", "title")),
	]

	for doctype, docname, fieldnames in targets:
		if not frappe.db.exists(doctype, docname):
			continue
		for fieldname in fieldnames:
			current = frappe.db.get_value(doctype, docname, fieldname)
			if current not in stock_labels or current == target:
				continue
			if frappe.db.exists(doctype, {fieldname: target}):
				print(
					f"xunoia_whitelabel: skipped setting {doctype} {docname}.{fieldname} "
					f"to {target!r} -- already in use by another {doctype} record."
				)
				continue
			frappe.db.set_value(doctype, docname, fieldname, target)


def _remove_xunoia_self_icon():
	"""
	Delete the Desktop Icon Frappe auto-generates for this app itself.

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

	Looked up through get_app_desktop_icon() (frappe/desk/doctype/desktop_icon/
	desktop_icon.py) -- core's own helper, also used internally by
	create_desktop_icons_from_installed_apps() and
	create_desktop_icons_from_workspace() to find an app's self icon. It
	filters on `icon_type == "App"` *and* `app == app_name`, not `app`
	alone -- see _remove_frappe_framework_icon below for why `app` by
	itself is not a safe filter on every app.

	Deleted, not hidden (an earlier version of this function only set
	`hidden`): xunoia_whitelabel defines no workspaces of its own, so no
	other Desktop Icon anywhere has `parent_icon` pointing at this one --
	unlike the frappe tile below, there is nothing that would get
	orphaned onto the main grid by removing it.

	Durability: xunoia_whitelabel ships no desktop_icon/ fixture, so
	nothing re-imports this row on `bench migrate`. Its only creation
	path, create_desktop_icons_from_installed_apps(), runs once via the
	after_app_install hook (at `bench install-app` time) and once via the
	v16_0 auto_generate_desktop_icon_and_sidebar patch (tracked in Patch
	Log, never reruns) -- so a deleted row here stays deleted. This stays
	idempotent and in after_migrate anyway, in case a future reinstall
	recreates it.
	"""
	icon_name = get_app_desktop_icon("xunoia_whitelabel")
	if icon_name:
		frappe.delete_doc(
			"Desktop Icon", icon_name, ignore_permissions=True, force=True, ignore_missing=True
		)


def _remove_frappe_framework_icon():
	"""
	Delete the Desktop Icon shipped for the framework's own self tile, and
	hide (not delete) the nine Framework-internal module tiles parented
	to it: Automation, Build, Data, Email, Integrations, Printing, System,
	Users, Website (all frappe/desktop_icon/*.json, each with
	`parent_icon: "Framework"`).

	Unlike xunoia_whitelabel, frappe does NOT rely on
	create_desktop_icons_from_installed_apps() for this tile -- it ships a
	hand-authored fixture at frappe/desktop_icon/framework.json:
	icon_type "App", app "frappe", label "Framework" (not "Frappe
	Framework" -- the app_title in hooks.py is display text for the
	app-switcher/about dialog, a separate thing from this icon's actual
	label/docname). Looked up via get_app_desktop_icon("frappe") -- i.e.
	{"icon_type": "App", "app": "frappe"} -- not a bare `{"app": "frappe"}`
	filter: frappe ships *eleven* Desktop Icon rows with app == "frappe"
	(Framework plus its nine children below, plus the unrelated top-level
	"My Workspaces"), so `app` alone is not a unique match.

	Why the nine children must be hidden here too: this function
	previously only set `hidden` on "Framework" itself (no deletion). That
	shipped, and a "Frappe Framework"-ish icon still appeared on the main
	grid afterwards, routing to /desk/build -- which was never "Framework"
	surviving; it was "Build" escaping. frappe/desk/page/desktop/desktop.js
	prepare() filters hidden icons OUT before building the parent/child
	map, so once "Framework" is hidden (or, as here, deleted and therefore
	absent), each of its nine children -- in their shipped state,
	hidden: 0 -- no longer finds its parent in that map and is pushed onto
	the main grid as its own top-level tile instead of staying nested
	inside "Framework"'s modal. Removing the parent without also hiding
	the children doesn't remove frappe's framework plumbing from the home
	page, it *scatters* it into nine separate tiles.

	The children are hidden, not deleted: Users, System Settings, Email,
	Website etc. are real, still-useful destinations for whoever
	administers this site -- just not wanted cluttering the main grid once
	their parent folder is gone. Hiding keeps them reachable from the
	Removed/Hidden Icons pane, the Awesomebar, or a direct URL.

	Durability: frappe/desktop_icon/framework.json is a fixture, and
	frappe.model.sync.sync_for() re-imports every installed app's
	desktop_icon/*.json files on *every* `bench migrate`
	(app_level_folders in frappe/model/sync.py), before after_migrate
	hooks run -- so a deleted "Framework" row is recreated by the fixture
	sync at the start of the very next migrate, then deleted again by this
	function at that migrate's end. Net effect: absent at the end of every
	migrate, same as a hidden-flag fix would be, except -- deliberately,
	per this change's intent -- not recoverable from the Removed/Hidden
	Icons pane the way a hidden icon would be. The nine children's
	`hidden` flag is not reset by that same fixture re-sync (they ship
	hidden: 0 on disk, so sync_for() would put them back to visible every
	migrate too) -- this function re-hides them every after_migrate run
	for the same reason _show_crm_icon below re-shows CRM every run.
	"""
	icon_name = get_app_desktop_icon("frappe")
	if not icon_name:
		return
	children = frappe.get_all("Desktop Icon", filters={"parent_icon": icon_name}, pluck="name")
	for child in children:
		if not frappe.db.get_value("Desktop Icon", child, "hidden"):
			frappe.db.set_value("Desktop Icon", child, "hidden", 1)
	frappe.delete_doc("Desktop Icon", icon_name, ignore_permissions=True, force=True, ignore_missing=True)


def _show_crm_icon():
	"""
	Un-hide the stock "CRM" Desktop Icon so it takes the main desktop
	grid's place vacated by XunoiaERP and Frappe Framework above.

	ERPNext ships this as a hand-authored fixture,
	erpnext/desktop_icon/crm.json: icon_type "Link", link_type "Workspace
	Sidebar", link_to "CRM" (the CRM workspace), parent_icon "ERPNext",
	hidden 1. "CRM" is both its label and docname (Desktop Icon autoname:
	field:label) -- the same stable identifier core itself matches on (see
	rebrand_erpnext_workspace_labels / _remove_xunoia_self_icon above), not
	a guess from UI text.

	Its `parent_icon` ("ERPNext") does not need separate handling: that
	row (erpnext/desktop_icon/erpnext.json, icon_type "App") also ships
	hidden 1, and frappe/desk/page/desktop/desktop.js prepare() only nests
	a child under its parent when the parent survives the hidden-icons
	filter first; a child whose parent is hidden (or missing) is pushed
	onto the main grid as its own top-level tile instead. So un-hiding CRM
	alone is sufficient for it to render as a top-level icon.

	Only the `hidden` flag is touched -- link_to/icon_type/parent_icon stay
	exactly as the fixture defines them, so CRM's route and behaviour are
	unchanged. The row is never created if missing (e.g. ERPNext not
	installed, or the CRM workspace renamed/removed on this site) -- this
	only ever reveals an icon that already exists.
	"""
	if frappe.db.exists("Desktop Icon", "CRM") and frappe.db.get_value("Desktop Icon", "CRM", "hidden"):
		frappe.db.set_value("Desktop Icon", "CRM", "hidden", 0)


def _restore_hrms_desktop_icon_label():
	"""
	Put the "Frappe HR" Desktop Icon's label back to stock if an earlier
	version of this app renamed it in the database.

	That version wrote the brand name straight into `Desktop Icon.label`.
	Reverting the code does not undo the write, so a site that ran it keeps
	a row named "Frappe HR" labelled "XunoiaHR". The desktop UI matches the
	nine child tiles to their parent by comparing their `parent_icon`
	("Frappe HR") with the parent's label (desktop.js prepare()), so that
	row must carry its stock label again -- the rebrand is now done by a
	Translation (see _ensure_brand_translations) and needs the label intact.

	Deliberately narrow: only acts when the current label is exactly the
	HR brand name this app would have written, so a label an administrator
	chose themselves is left alone, and never when another row already owns
	the stock label (Desktop Icon.label is unique). A site that never ran the
	old code, or has no hrms, does nothing.
	"""
	brand = frappe.get_single("Xunoia Brand Settings")
	written_by_old_version = brand.hr_product_name or "XunoiaHR"
	current = frappe.db.get_value("Desktop Icon", "Frappe HR", "label")
	if current == written_by_old_version and not frappe.db.exists("Desktop Icon", {"label": "Frappe HR"}):
		frappe.db.set_value("Desktop Icon", "Frappe HR", "label", "Frappe HR")


def _ensure_brand_translations():
	"""
	Rebrand stock Frappe strings that reach the Desk through __() by adding
	Translation records, instead of editing the data they are read from.

	Used for the Frappe HR (hrms) desktop tile. The tile title and its
	tooltip are rendered as `__(icon.label)`
	(frappe/public/js/frappe/ui/desktop_icon.html), so a Translation of
	"Frappe HR" changes what is displayed while `Desktop Icon.label` stays
	"Frappe HR". That matters: Desktop Icon.label is also its docname
	(autoname: field:label) and the desktop UI matches on it --
	`icon_map[icon.label]` / `parent_icon` in desktop.js prepare() attaches
	the nine HR child tiles to their parent, and get_route() looks sidebars
	up by `icon.label.toLowerCase()`. Relabelling the row would detach the
	children and break routing; a Translation cannot.

	Translations are delivered to the browser for every language, English
	included (boot.py: bootinfo.__messages = get_all_translations(lang)),
	and user Translation records override the app's own. Because the data
	is never changed, a user's saved Desktop Layout snapshot cannot show a
	stale label either.

	Idempotent and non-clobbering: a (language, source text) pair that
	already has a Translation is left alone, so an administrator's own
	wording is never overwritten. Creating the record through the ORM runs
	Translation.on_update, which clears the translation caches. Does nothing
	visible on a site without hrms: no rendered string matches the source.
	"""
	brand = frappe.get_single("Xunoia Brand Settings")
	translations = {
		"Frappe HR": brand.hr_product_name or "XunoiaHR",
	}

	for language in _languages_in_use():
		for source_text, translated_text in translations.items():
			if frappe.db.exists("Translation", {"language": language, "source_text": source_text}):
				continue
			frappe.get_doc(
				{
					"doctype": "Translation",
					"language": language,
					"source_text": source_text,
					"translated_text": translated_text,
				}
			).insert(ignore_permissions=True)


def _languages_in_use():
	"""English, the site language and every language an enabled user has chosen.

	User translations are looked up per language (and its parent, so "en-US"
	falls back to "en"), so each language in use needs its own record.
	"""
	languages = {"en"}
	if system_language := frappe.get_system_settings("language"):
		languages.add(system_language)
	languages.update(
		frappe.get_all("User", filters={"enabled": 1, "language": ["is", "set"]}, pluck="language")
	)
	return sorted(language for language in languages if frappe.db.exists("Language", language))

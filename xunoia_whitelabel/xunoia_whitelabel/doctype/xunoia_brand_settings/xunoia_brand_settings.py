# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary

import frappe
from frappe.model.document import Document
from frappe.utils import cint

# Seeded by install._ensure_brand_settings() into blank fields, and the value
# every copy written elsewhere starts from when a field was never saved.
BRAND_DEFAULTS = {
	"product_name": "XunoiaERP",
	"hr_product_name": "XunoiaHR",
	"company_name": "Xunoia",
	"logo": "/assets/xunoia_whitelabel/images/logo.png",
	"favicon": "/assets/xunoia_whitelabel/images/favicon.png",
	"website_url": "https://xunoia.com",
	"documentation_url": "https://docs.xunoia.com",
	"support_url": "https://support.xunoia.com",
}

# Brand Settings toggle -> the System Settings flag Frappe itself respects.
#   disable_system_update_notification: server-side update check / notice.
#   disable_product_suggestion: frappe/public/js/frappe/ui/sidebar/sidebar.js
#     setup_promotional_banners() skips the "Switch to Frappe CRM" (CRM
#     module) and "Switch to Helpdesk" (Support module) sidebar banners when
#     frappe.defaults.is_enabled("disable_product_suggestion").
SYSTEM_SETTINGS_TOGGLES = {
	"disable_update_notification": "disable_system_update_notification",
	"disable_product_suggestion": "disable_product_suggestion",
}

# Help dropdown rows install.py adds, keyed by the brand field they link to.
HELP_ROW_URL_FIELDS = {
	"Xunoia Documentation": "documentation_url",
	"Xunoia Support": "support_url",
}


class XunoiaBrandSettings(Document):
	def on_update(self):
		sync_system_settings(self)
		self._propagate_brand_changes()
		# Brand values reach users through several caches: this doc
		# (frappe.get_cached_doc in boot.py / www/website_context.py), each
		# user's cached boot info, rendered website pages (login, portal), and
		# translations. A full clear is the only call that covers all of them,
		# and saving brand settings is a rare admin action.
		frappe.clear_cache()

	def _propagate_brand_changes(self):
		"""
		Carry a changed brand value into every record install.py copied it
		into, so the Brand Settings form stays the single source of truth.

		Each copy is only rewritten while it still holds the previous brand
		value, i.e. while it is still the copy this app wrote. A copy an
		administrator has since customised is left alone, matching the
		never-clobber rule in install.py.
		"""
		before = self.get_doc_before_save()
		if not before:
			return

		def change(fieldname):
			old = before.get(fieldname) or BRAND_DEFAULTS[fieldname]
			new = self.get(fieldname) or BRAND_DEFAULTS[fieldname]
			return (old, new) if old != new else None

		if product_name := change("product_name"):
			old, new = product_name
			for doctype in ("Website Settings", "System Settings"):
				if frappe.db.get_single_value(doctype, "app_name") == old:
					frappe.db.set_single_value(doctype, "app_name", new)
			# Local import: install.py imports this module at load time.
			from xunoia_whitelabel.install import rebrand_erpnext_workspace_labels

			rebrand_erpnext_workspace_labels(previous_product_name=old)

		if logo := change("logo"):
			old, new = logo
			if frappe.db.get_single_value("Navbar Settings", "app_logo") == old:
				frappe.db.set_single_value("Navbar Settings", "app_logo", new)

		for item_label, url_field in HELP_ROW_URL_FIELDS.items():
			if url := change(url_field):
				old, new = url
				for row_name in frappe.get_all(
					"Navbar Item",
					filters={
						"parenttype": "Navbar Settings",
						"parentfield": "help_dropdown",
						"item_label": item_label,
						"route": old,
					},
					pluck="name",
				):
					frappe.db.set_value("Navbar Item", row_name, "route", new)

		if hr_product_name := change("hr_product_name"):
			old, new = hr_product_name
			for translation_name in frappe.get_all(
				"Translation",
				filters={"source_text": "Frappe HR", "translated_text": old},
				pluck="name",
			):
				translation = frappe.get_doc("Translation", translation_name)
				translation.translated_text = new
				translation.save(ignore_permissions=True)


def sync_system_settings(settings):
	"""Mirror the Brand Settings toggles to Frappe's supported System Settings flags.

	Written without saving System Settings, so its validate() can never fail a
	migrate over some unrelated field. System Settings.on_update would also
	copy each changed field into the global defaults, which is where Desk JS
	reads them from (frappe.defaults.is_enabled), so do that part here too.
	frappe.db.set_default clears the global cache, including cached boot info.
	"""
	for brand_field, system_field in SYSTEM_SETTINGS_TOGGLES.items():
		desired_value = cint(settings.get(brand_field))
		if cint(frappe.db.get_single_value("System Settings", system_field)) != desired_value:
			frappe.db.set_single_value("System Settings", system_field, desired_value, update_modified=False)
		if cint(frappe.db.get_default(system_field)) != desired_value:
			frappe.db.set_default(system_field, desired_value)

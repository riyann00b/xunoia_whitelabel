# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary

import frappe
from frappe.model.document import Document
from frappe.utils import cint

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


class XunoiaBrandSettings(Document):
	def on_update(self):
		sync_system_settings(self)
		# Brand values are read via frappe.get_cached_doc() in boot.py and
		# www/website_context.py. Clear the doc cache so the next boot /
		# page render picks up the change immediately instead of waiting
		# for the default cache TTL to expire.
		frappe.clear_document_cache("Xunoia Brand Settings", "Xunoia Brand Settings")


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

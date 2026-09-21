# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary

import frappe
from frappe.model.document import Document
from frappe.utils import cint


class XunoiaBrandSettings(Document):
	def on_update(self):
		_sync_update_notification_setting(self.disable_update_notification)
		# Brand values are read via frappe.get_cached_doc() in boot.py and
		# www/website_context.py. Clear the doc cache so the next boot /
		# page render picks up the change immediately instead of waiting
		# for the default cache TTL to expire.
		frappe.clear_document_cache("Xunoia Brand Settings", "Xunoia Brand Settings")


def _sync_update_notification_setting(disable_update_notification):
	"""Keep Frappe's supported update-notification switch in sync."""
	disable_update_notification = cint(disable_update_notification)
	current_value = cint(frappe.get_single_value("System Settings", "disable_system_update_notification"))
	if current_value != disable_update_notification:
		frappe.db.set_single_value(
			"System Settings",
			"disable_system_update_notification",
			disable_update_notification,
			update_modified=False,
		)

# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary

import frappe
from frappe.model.document import Document


class XunoiaBrandSettings(Document):
	def on_update(self):
		# Brand values are read via frappe.get_cached_doc() in boot.py and
		# www/website_context.py. Clear the doc cache so the next boot /
		# page render picks up the change immediately instead of waiting
		# for the default cache TTL to expire.
		frappe.clear_document_cache("Xunoia Brand Settings", "Xunoia Brand Settings")

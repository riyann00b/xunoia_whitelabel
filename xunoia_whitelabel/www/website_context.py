# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary
"""
update_website_context hook (see hooks.py).

Runs when a Portal/website page's Jinja context is built, letting us inject
Xunoia brand values into every server-rendered website template (login page,
web forms, print-in-browser, 404/500 error pages) without editing any
frappe/erpnext template file directly.

EVIDENCE: DOCUMENTATION (hooks.md "Website Context" reference). The static
`website_context` dict in hooks.py handles the simple favicon/splash_image
overrides; this callable handles the rest, since those two need a DB read
(Xunoia Brand Settings) that a static hooks.py dict cannot perform.
"""

import frappe


def update_context(context):
	settings = frappe.get_cached_doc("Xunoia Brand Settings")

	context.app_name = settings.product_name or "XunoiaERP"
	context.brand_html = settings.company_name or "Xunoia"
	context.brand_name = settings.company_name or "Xunoia"
	context.website_logo = settings.logo or "/assets/xunoia_whitelabel/images/logo.png"
	context.favicon = settings.favicon or "/assets/xunoia_whitelabel/images/favicon.png"
	context.site_url = settings.website_url or frappe.utils.get_url()
	if context.get("title") == "Login":
		context.title = f"{context.app_name} - {context.title}"

	return context

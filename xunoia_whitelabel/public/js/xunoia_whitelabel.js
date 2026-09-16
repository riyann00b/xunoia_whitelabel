// Copyright (c) 2026, Xunoia Technologies Private Limited
// License: Proprietary
//
// Loaded via app_include_js, AFTER frappe's and erpnext's own desk bundles
// (apps are installed in order, and asset injection follows install order),
// so every reassignment below is a safe monkey-patch of an already-defined
// `frappe.*` value, not a race.
//
// SOURCE for the override point:
//   frappe/frappe/public/js/frappe/ui/toolbar/about.js defines
//   `frappe.ui.toolbar.show_about`, bound to the Help dropdown's "About" row.
//   Confirmed by directory listing on the `develop` branch. Frappe does not
//   expose a hook or config value to change the About dialog's *content* —
//   a JS override (tier 6 in the brief's priority list) is the highest
//   mechanism actually available for this one surface.

(function () {
	"use strict";

	function get_branding() {
		return (frappe.boot && frappe.boot.xunoia && frappe.boot.xunoia.branding) || {};
	}

	// ------------------------------------------------------------------
	// 1. About dialog
	// ------------------------------------------------------------------
	if (frappe.ui && frappe.ui.toolbar && typeof frappe.ui.toolbar.show_about === "function") {
		frappe.ui.toolbar.show_about = function () {
			const b = get_branding();
			const versions_html = Object.keys(frappe.boot.versions || {})
				.sort()
				.map((app) => `<li>${app}: v${frappe.boot.versions[app]}</li>`)
				.join("");

			const d = new frappe.ui.Dialog({
				title: __("About {0}", [b.product_name || "Xunoia"]),
			});

			$(d.body).html(`
				<div>
					${b.logo ? `<img src="${b.logo}" style="max-height: 40px; margin-bottom: 12px;">` : ""}
					<p>${__("{0} is built on a modern, open framework.", [b.company_name || "Xunoia"])}</p>
					<ul>${versions_html}</ul>
					<hr>
					<p>
						${b.website_url ? `<a href="${b.website_url}" target="_blank">${__("Website")}</a>` : ""}
						${b.documentation_url ? ` &middot; <a href="${b.documentation_url}" target="_blank">${__("Documentation")}</a>` : ""}
						${b.support_url ? ` &middot; <a href="${b.support_url}" target="_blank">${__("Support")}</a>` : ""}
					</p>
				</div>
			`);
			d.show();
		};
	} else {
		// Defensive: if a future core version renames/removes show_about,
		// fail loudly in the console rather than silently leaking the
		// stock "About Frappe" dialog to a customer.
		console.warn(
			"[xunoia_whitelabel] frappe.ui.toolbar.show_about not found — " +
				"About dialog override did not apply. Verify against the " +
				"installed frappe version."
		);
	}

	// ------------------------------------------------------------------
	// 2. Defense-in-depth for the Help dropdown.
	// boot.py already strips/relabels rows server-side before they reach
	// the browser (the correct, primary fix). This is a no-op in the
	// normal case; it only matters if something renders the navbar from a
	// stale cached `frappe.boot` that predates a boot.py deploy.
	// ------------------------------------------------------------------
	frappe.after_ajax &&
		frappe.after_ajax(function () {
			$(".navbar .dropdown-menu")
				.find('[data-label="Frappe Support"]')
				.closest("li")
				.remove();
		});

	// ------------------------------------------------------------------
	// 3. Browser tab title / page title fallback.
	// frappe.boot.sitename / document title composition already reads
	// Website Settings + System Settings app_name in most places; this is
	// a narrow safety net for any hard-coded "Frappe" left in a page title
	// template.
	// ------------------------------------------------------------------
	const b = get_branding();
	if (b.product_name && document.title && /frappe/i.test(document.title)) {
		document.title = document.title.replace(/frappe/gi, b.product_name);
	}
})();

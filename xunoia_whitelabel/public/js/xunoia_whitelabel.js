(function () {
	"use strict";

	const get_branding = () =>
		(frappe.boot && frappe.boot.xunoia && frappe.boot.xunoia.branding) || {};
	const escape_html = (value) => frappe.utils.escape_html(String(value || ""));
	const safe_url = (value) => (/^https?:\/\//i.test(value || "") ? value : "");

	function show_about() {
		const b = get_branding();
		const product_name = escape_html(b.product_name || "XunoiaERP");
		const hr_product_name = escape_html(b.hr_product_name || "XunoiaHR");
		const company_name = escape_html(b.company_name || "Xunoia");
		const logo = escape_html(b.logo);
		const links = [
			["Website", safe_url(b.website_url)],
			["Documentation", safe_url(b.documentation_url)],
			["Support", safe_url(b.support_url)],
		]
			.filter(([, url]) => url)
			.map(([label, url]) => `<a href="${escape_html(url)}" target="_blank" rel="noreferrer">${__(label)}</a>`)
			.join(" &middot; ");

		const versions_html = Object.entries(frappe.boot.versions || {})
			.filter(([app]) => !["frappe", "xunoia_whitelabel"].includes(app))
			.map(([app, version]) => {
				const label =
					app === "erpnext" ? product_name : app === "hrms" ? hr_product_name : escape_html(app);
				return `<li>${label}: v${escape_html(version)}</li>`;
			})
			.join("");

		const dialog = new frappe.ui.Dialog({
			title: __("About {0}", [product_name]),
		});
		$(dialog.body).html(`
			<div class="xunoia-about">
				${logo ? `<img src="${logo}" alt="${company_name}" style="max-height: 48px; margin-bottom: 12px;">` : ""}
				<p>${__("{0} is built for modern business operations.", [company_name])}</p>
				<ul>${versions_html}</ul>
				${links ? `<hr><p>${links}</p>` : ""}
			</div>
		`);
		dialog.show();
	}

	// Frappe v16 routes the standard Help action through this bridge.
	if (frappe.ui?.toolbar) {
		frappe.ui.toolbar.show_about = show_about;
	}
	if (frappe.ui?.misc) {
		frappe.ui.misc.about = show_about;
		frappe.ui.misc.about_dialog = null;
	}

	const brand = get_branding();
	if (brand.product_name) {
		document.title = brand.product_name;
	}
	if (brand.favicon) {
		$('link[rel="shortcut icon"], link[rel="icon"]').attr("href", brand.favicon);
	}

	// Frappe v16's top-right avatar/profile menu (desktop.js setup_avatar())
	// builds its item list as a plain in-memory array and never touches
	// bootinfo.navbar_settings, so the boot.py filter can't reach it there.
	// Every Desk dropdown menu (avatar, sidebar header, breadcrumbs,
	// workspace) is built through this one shared factory, so patching it
	// here catches this menu -- and anywhere else these labels could
	// reappear -- without a DOM-selector guess. (The previous `[data-label]`
	// selector never matched anything: frappe's menu.js renders items as
	// `<span class="menu-item-title">`, with no data-label attribute.)
	if (frappe.ui && typeof frappe.ui.create_menu === "function") {
		const hidden_labels = new Set((frappe.boot?.xunoia?.hidden_menu_labels) || []);
		const disable_desk_right_click = frappe.boot?.xunoia?.disable_desk_right_click !== false;
		const original_create_menu = frappe.ui.create_menu;
		frappe.ui.create_menu = function (opts) {
			// The Desktop page's only two right-click menus (desktop.js
			// setup_context_menu() "Edit Layout"/"Reset Layout", and
			// setup_edit_menu() per-icon "Edit") are built through this same
			// factory with `right_click: true`, and neither is gated by a
			// role/permission check in core -- any logged-in user gets them.
			// Nothing else in frappe or erpnext passes right_click (checked),
			// so skipping construction entirely here -- no listener ever gets
			// bound, see menu.js setup_menu_toggle() -- hides both surfaces
			// for every end user with no DOM/CSS guess.
			if (disable_desk_right_click && opts?.right_click) {
				return undefined;
			}
			if (hidden_labels.size && Array.isArray(opts?.menu_items)) {
				opts.menu_items = opts.menu_items.filter((item) => !hidden_labels.has(item?.label));
			}
			return original_create_menu.call(this, opts);
		};
	}
})();

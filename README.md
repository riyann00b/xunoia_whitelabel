# xunoia_whitelabel

Customer-facing white-label branding for Frappe Framework v16 + ERPNext v16.

`Frappe Framework + ERPNext + xunoia_whitelabel = XunoiaERP`

The implementation keeps the source-of-truth audit in code comments and uses
the supported Frappe hooks described below.

## Install

```bash
bench get-app xunoia_whitelabel /path/to/xunoia_whitelabel   # local path, or a git remote
bench --site your-site.local install-app xunoia_whitelabel
bench --site your-site.local migrate
bench build --app xunoia_whitelabel
bench restart   # or: pilot bench restart
```

## Configure

After install, open **Xunoia Brand Settings** in the desk (Awesomebar ->
"Xunoia Brand Settings") and fill in / confirm:

- Product Name, Company Name
- Logo, Favicon
- Website / Documentation / Support URLs

Defaults (`XunoiaERP` / `Xunoia` / `https://xunoia.com` / …) are seeded automatically by
`after_install` / `after_migrate` the first time, and never overwritten once
you've changed them.

## Assets you must supply

The repository includes default `logo.png` and `favicon.png` assets. Replace
them with your production artwork before your first `pilot build` if needed:

```
xunoia_whitelabel/public/images/logo.png
xunoia_whitelabel/public/images/favicon.png
```

(Referenced by `hooks.py`'s `website_context` dict.)

## Development cycle

Pilot workflow:

- Python, hooks, or boot changes: run `pilot frappe --site your-site migrate`
  when configuration or DocTypes changed, then restart the development or
  production workload as appropriate.
- JavaScript/CSS changes: run `pilot build --apps xunoia_whitelabel` and clear
  the site/browser cache.
- Database branding changes: run the site migration; the app's hooks are
  idempotent.
# xunoia_whitelabel

# xunoia_whitelabel

Customer-facing white-label branding for Frappe Framework v16 + ERPNext v16.

`Frappe Framework + ERPNext + xunoia_whitelabel = Xunoia`

See the accompanying engineering report for the full source audit, branding
map, upgrade-safety analysis, and verification steps. This README covers
only install/dev commands.

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

Defaults (`Xunoia` / `https://xunoia.com` / …) are seeded automatically by
`after_install` / `after_migrate` the first time, and never overwritten once
you've changed them.

## Assets you must supply

This repository ships no binary image assets. Add these before your first
`bench build`:

```
xunoia_whitelabel/public/images/logo.png
xunoia_whitelabel/public/images/favicon.png
```

(Referenced by `hooks.py`'s `website_context` dict.)

## Development cycle

See the report's "Pilot Workflow" section for the full breakdown of what
needs reload vs. restart vs. migrate vs. asset build vs. browser refresh for
each kind of change (Python / JS / CSS / DocType / boot).
# xunoia_whitelabel

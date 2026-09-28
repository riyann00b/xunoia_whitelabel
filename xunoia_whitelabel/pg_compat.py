# Copyright (c) 2026, Xunoia Technologies Private Limited
# License: Proprietary

"""
PostgreSQL compatibility patches for pypika query-builder methods that
Frappe/ERPNext call unconditionally, assuming a MariaDB backend.

Applied at hooks.py import time, and again from the before_request /
before_job hooks: in production frappe.get_hooks() serves the hooks dict
from the Redis cache, so a freshly forked web or RQ worker may never import
hooks.py itself. apply() is idempotent, so calling it on every request/job
costs one attribute check.
"""

import frappe
from pypika.queries import QueryBuilder
from pypika.terms import Index
from pypika.utils import builder


def apply():
	if getattr(QueryBuilder.force_index, "_xunoia_pg_safe", False):
		return
	_patch_force_index()


def _patch_force_index():
	"""
	pypika's QueryBuilder.force_index() always emits MySQL's
	`FORCE INDEX (...)` hint syntax; PostgreSQL has no index-hint syntax
	at all, so the stock method breaks any caller on a Postgres site
	(e.g. erpnext.accounts.report.financial_statements.get_accounting_entries,
	which backs Profit and Loss / Balance Sheet / Cash Flow):

	    psycopg2.errors.SyntaxError: syntax error at or near "INDEX"

	Only record the hint when actually targeting MariaDB/MySQL; make it a
	silent no-op (matching Postgres, which has no equivalent) everywhere
	else. Patching the shared pypika base class -- rather than the one
	erpnext call site -- covers every current and future force_index()
	caller in frappe/erpnext, not just this report.
	"""

	@builder
	def postgres_safe_force_index(self, term, *terms):
		if frappe.db and frappe.db.db_type != "mariadb":
			return

		for t in (term, *terms):
			if isinstance(t, Index):
				self._force_indexes.append(t)
			elif isinstance(t, str):
				self._force_indexes.append(Index(t))

	postgres_safe_force_index._xunoia_pg_safe = True
	QueryBuilder.force_index = postgres_safe_force_index

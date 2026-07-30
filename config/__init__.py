"""
If you're on MySQL (DB_ENGINE=mysql — e.g. a cPanel/WhoGoHost database),
Django's mysql backend expects a module called MySQLdb. We use PyMySQL
instead of the usual mysqlclient driver specifically because PyMySQL is
pure Python — it installs from a wheel with no C compiler or mysql_config
needed, which matters on shared hosting (cPanel's "Setup Python App")
where you can't install system build tools yourself. This shim makes
PyMySQL present itself as MySQLdb so Django's mysql backend just works.

Harmless no-op if PyMySQL isn't installed (e.g. you're on Postgres or
SQLite) — the import is wrapped so it never breaks those setups.
"""

try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

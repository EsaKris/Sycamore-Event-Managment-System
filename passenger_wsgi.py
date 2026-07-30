"""
Entry point for cPanel's "Setup Python App" (Passenger).

When you create the Python App in cPanel, it auto-generates a file at
this exact path/name with a virtualenv-activation shim already at the
top (something like an `os.execl(...)` re-exec into the app's own
virtualenv's Python). DO NOT delete that shim if cPanel already wrote
one — just make sure whatever's below it matches the three lines here.
If cPanel hasn't generated anything yet (fresh app), this file works
as-is with no edits needed.

See DEPLOY_CPANEL.md for the full setup walkthrough.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from config.wsgi import application

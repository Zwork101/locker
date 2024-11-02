import sys

sys.path.insert(0, "/var/www/Locker")

from locker.app import app

application = app

#!/usr/bin/env python
import os
import sys
from django.core.management.commands.runserver import Command as RunserverCommand
import socket


# Get local IP dynamically
def get_local_ip():
    try:
        # Get hostname
        hostname = socket.gethostname()
        # Get local IP
        local_ip = socket.gethostbyname(hostname)
        return local_ip
    except:
        return "127.0.0.1"


# Custom server configuration
HOST = get_local_ip()  # Dynamic local IP
PORT = 8000  # Default Django port

# Override default server settings
RunserverCommand.default_addr = HOST
RunserverCommand.default_port = PORT


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scraper_mng.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

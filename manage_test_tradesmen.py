#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    from django.core.management import execute_from_command_line
    args = [sys.argv[0], "manage_test_tradesmen"] + sys.argv[1:]
    execute_from_command_line(args)

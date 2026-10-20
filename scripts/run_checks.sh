#!/usr/bin/env bash
# Quick verification script for PMS
set -e

echo "Running Django system checks..."
python manage.py check

echo "Running migrations..."
python manage.py migrate --noinput

echo "Running test suite..."
python manage.py test

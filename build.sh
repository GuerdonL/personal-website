#!/bin/bash
#
# Build script for Guerdon's personal website.
# Parses content.md and assembles index.html from templates.
#

set -e
python3 build.py

#!/usr/bin/env bash
# netlify_build.sh
#
# Full build for Netlify's CI: runs build_beta.py to produce fahm_beta.html
# from the template + corpus data, then assembles the dist/ folder that
# Netlify publishes (per netlify.toml: publish = "dist").
#
# Replaces the old manual flow of:
#   python3 build_beta.py  ->  copy files into dist/  ->  netlify deploy
# This script does the copy step so Netlify can do it automatically on
# every push to main.

set -euo pipefail

echo "Running build_beta.py..."
python3 build_beta.py

echo "Assembling dist/..."
rm -rf dist
mkdir -p dist

cp landing.html dist/index.html
cp fahm_beta.html dist/reader.html
cp privacy.html dist/privacy.html
cp terms.html dist/terms.html
# Note: Netlify Functions deploy separately per netlify.toml's
# [functions] functions = "netlify/functions" — they do NOT need to be
# copied into dist/. (Your old local dist/ had a stray "netlify" folder
# and "logo.png" inside it — neither is referenced by any page or by
# netlify.toml, so they're left out here. If logo.png turns out to be
# used somewhere I missed, let me know and I'll add it back.)

echo "dist/ contents:"
ls -la dist/

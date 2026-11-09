#!/usr/bin/env bash
set -euo pipefail
if grep -R -n 'innerHTML' app/frontend/assets; then exit 1; fi
if grep -R -nE '<(script|link)[^>]+(src|href)=["\x27]https?://' app/frontend; then exit 1; fi
echo "check_frontend: OK"

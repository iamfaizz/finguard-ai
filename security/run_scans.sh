#!/usr/bin/env bash
# Step 8.3 automated scans. Run from the repo root. Install once:
#   pip install pip-audit      and gitleaks from https://github.com/gitleaks/gitleaks/releases
set -u
fail=0
echo "== gitleaks =="
gitleaks detect --source . --config security/.gitleaks.toml --no-banner || fail=1
for req in backend ml-fraud ml-forecast advisor; do
  if [ -f "$req/requirements.txt" ]; then
    echo "== pip-audit: $req =="
    pip-audit -r "$req/requirements.txt" || fail=1
  fi
done
if [ -f frontend/package.json ]; then
  echo "== npm audit (frontend) =="
  (cd frontend && npm audit --omit=dev --audit-level=high) || fail=1
fi
[ $fail -eq 0 ] && echo "ALL CLEAN" || echo "FINDINGS - review above"
exit $fail

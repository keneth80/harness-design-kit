#!/bin/bash
# 하네스 회귀 테스트 + 플러그인 검증
# 사용: bash tests/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/sync_lib.py --check
python3 -m unittest discover -s tests -p 'test_*.py' "$@"
if command -v claude >/dev/null 2>&1; then
  claude plugin validate . >/dev/null && echo "marketplace: Validation passed"
  for p in plugins/*/; do
    claude plugin validate "$p" | tail -1 | sed "s|^|$(basename "$p"): |"
  done
else
  echo "(claude CLI가 없어 plugin validate는 건너뜀)"
fi

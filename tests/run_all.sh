#!/bin/bash
# 하네스 킷 훅 회귀 테스트 실행기
# 사용법: bash tests/run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
python3 -m unittest discover -s . -p 'test_*.py' -v

#!/bin/bash
# ============================================================================
# switch.sh — 하네스 프로파일 전환 (lite ↔ full)
#
# 사용법: bash .claude/profiles/switch.sh <lite|full>
#
# 동작:
#   - profiles/<프로파일>/settings.json → .claude/settings.json 복사
#   - full 전용 자산(profiles/full/{commands,agents,skills})을
#     full이면 루트(.claude/{commands,agents,skills})로 복사, lite면 루트에서 제거
#   - harness.config.json의 profile 필드 갱신 (파일이 있을 때만)
#
# 훅 스크립트(.claude/hooks/)는 삭제하지 않는다 — settings.json 등록 여부로만 제어.
# ============================================================================
set -euo pipefail

PROFILE="${1:?사용법: bash .claude/profiles/switch.sh <lite|full>}"
PROFILES_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$(dirname "$PROFILES_DIR")"
PROJECT_DIR="$(dirname "$CLAUDE_DIR")"

if [ ! -f "$PROFILES_DIR/$PROFILE/settings.json" ]; then
    echo "❌ 알 수 없는 프로파일: $PROFILE (lite 또는 full)" >&2
    exit 1
fi

# 1. settings.json 교체
cp "$PROFILES_DIR/$PROFILE/settings.json" "$CLAUDE_DIR/settings.json"

# 2. full 전용 자산 반영/제거
for kind in commands agents skills; do
    src="$PROFILES_DIR/full/$kind"
    [ -d "$src" ] || continue
    if [ "$PROFILE" = "full" ]; then
        cp -R "$src/." "$CLAUDE_DIR/$kind/"
    else
        # profiles/full에 있는 항목만 루트에서 제거 (lite 자산은 여기 없음)
        for item in "$src"/*; do
            [ -e "$item" ] || continue
            rm -rf "$CLAUDE_DIR/$kind/$(basename "$item")"
        done
    fi
done

# 3. harness.config.json profile 필드 갱신
CFG="$PROJECT_DIR/harness.config.json"
if [ -f "$CFG" ]; then
    python3 - "$CFG" "$PROFILE" <<'EOF'
import json, sys
path, profile = sys.argv[1], sys.argv[2]
try:
    with open(path) as f:
        cfg = json.load(f)
except Exception:
    cfg = {}
cfg = {**cfg, "profile": profile}
with open(path, "w") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
EOF
fi

echo "✅ 하네스 프로파일 전환 완료: $PROFILE"
if [ "$PROFILE" = "lite" ]; then
    echo "   (full 전용 훅/커맨드/에이전트는 비활성. 복원: bash .claude/profiles/switch.sh full)"
fi

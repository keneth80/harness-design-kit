#!/bin/bash
# ============================================================================
# setup-claude-optimization.sh — Claude Code 토큰 최적화 설정
# ============================================================================
#
# Opus 4.7 이후 증가한 토큰 소모를 줄이기 위한 최적화 설정을 적용합니다.
#
# 사용법:
#   bash setup-claude-optimization.sh                # 현재 프로젝트에 적용
#   bash setup-claude-optimization.sh ~/my-project    # 지정 프로젝트에 적용
#   bash setup-claude-optimization.sh --global        # 글로벌 설정만 적용
#
# 적용 항목:
#   1. settings.json — 프로젝트 레벨 (Git 지시어, IDE 연결 해제)
#   2. 환경변수 — 셸 프로필 (.zshrc/.bashrc)
#   3. 실행 alias — 최적화 플래그 포함 claude 실행  
#
# 참고:
#   - v2.1.108+ 기준
#   - ENABLE_PROMPT_CACHING_1H=1 로 캐시 TTL 1시간 복원 가능
#   - 기존 settings.json이 있으면 머지 (덮어쓰지 않음)
# ============================================================================

set -euo pipefail

# ── 색상 ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── 인자 파싱 ────────────────────────────────────────
GLOBAL_ONLY=false
PROJECT_DIR="."

if [ "${1:-}" = "--global" ]; then
    GLOBAL_ONLY=true
elif [ -n "${1:-}" ]; then
    PROJECT_DIR="$1"
fi

if [ "$GLOBAL_ONLY" = false ] && [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ 디렉토리가 없습니다: $PROJECT_DIR${NC}"
    exit 1
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Claude Code 토큰 최적화 설정${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ============================================================================
# 1. 프로젝트 settings.json (프로젝트 레벨)
# ============================================================================

if [ "$GLOBAL_ONLY" = false ]; then
    echo -e "${GREEN}[1/3] 프로젝트 settings.json 설정${NC}"

    SETTINGS_DIR="$PROJECT_DIR/.claude"
    SETTINGS_FILE="$SETTINGS_DIR/settings.json"

    mkdir -p "$SETTINGS_DIR"

    if [ -f "$SETTINGS_FILE" ]; then
        echo -e "  ${YELLOW}기존 settings.json 발견 — 머지합니다${NC}"

        # Python으로 JSON 머지 (jq 없는 환경 대응)
        python3 -c "
import json, sys

with open('$SETTINGS_FILE', 'r') as f:
    existing = json.load(f)

# 최적화 설정 추가 (기존 값 보존)
optimizations = {
    'includeGitInstructions': False,
    'autoConnectIde': False
}

for key, value in optimizations.items():
    if key not in existing:
        existing[key] = value
        print(f'  + {key}: {value}')
    else:
        print(f'  = {key}: {existing[key]} (기존 유지)')

with open('$SETTINGS_FILE', 'w') as f:
    json.dump(existing, f, indent=2, ensure_ascii=False)
    f.write('\n')
" 2>/dev/null || {
        echo -e "  ${YELLOW}Python3 없음 — 수동으로 추가해주세요:${NC}"
        echo '  "includeGitInstructions": false'
        echo '  "autoConnectIde": false'
    }
    else
        # 새로 생성 (기존 hooks 설정과 함께)
        cat > "$SETTINGS_FILE" << 'SETTINGS_EOF'
{
  "includeGitInstructions": false,
  "autoConnectIde": false,
  "hooks": {}
}
SETTINGS_EOF
        echo -e "  ${GREEN}✅ settings.json 생성 완료${NC}"
    fi
    echo ""
fi

# ============================================================================
# 2. 환경변수 (셸 프로필)
# ============================================================================

echo -e "${GREEN}[2/3] 환경변수 설정${NC}"

# 셸 프로필 감지
SHELL_PROFILE=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_PROFILE="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_PROFILE="$HOME/.bashrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_PROFILE="$HOME/.bash_profile"
fi

# 환경변수 블록
MARKER_START="# ── Claude Code Optimization (auto-generated) ──"
MARKER_END="# ── End Claude Code Optimization ──"

ENV_BLOCK=$(cat << 'ENV_EOF'
# ── Claude Code Optimization (auto-generated) ──

# [캐싱] TTL 1시간 복원 (v2.1.108+, 기본 5분 → 1시간)
export ENABLE_PROMPT_CACHING_1H=1

# [출력 상한] 파일 읽기, bash 출력, MCP 결과 토큰 제한
export BASH_MAX_OUTPUT_LENGTH=8000
export CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS=8000
export MAX_MCP_OUTPUT_TOKENS=8000

# [백그라운드 차단] 불필요한 자동 기능 비활성화
export ENABLE_CLAUDEAI_MCP_SERVERS=false
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1

# [Git 지시어] settings.json과 중복 보장
export CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1

# [glob] gitignore 준수
export CLAUDE_CODE_GLOB_NO_IGNORE=false

# ── End Claude Code Optimization ──
ENV_EOF
)

if [ -n "$SHELL_PROFILE" ]; then
    # 기존 블록이 있으면 교체
    if grep -q "$MARKER_START" "$SHELL_PROFILE" 2>/dev/null; then
        echo -e "  ${YELLOW}기존 설정 블록 발견 — 업데이트합니다${NC}"
        # sed로 기존 블록 제거 후 새 블록 추가
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "/$MARKER_START/,/$MARKER_END/d" "$SHELL_PROFILE"
        else
            sed -i "/$MARKER_START/,/$MARKER_END/d" "$SHELL_PROFILE"
        fi
    fi

    echo "" >> "$SHELL_PROFILE"
    echo "$ENV_BLOCK" >> "$SHELL_PROFILE"
    echo -e "  ${GREEN}✅ $SHELL_PROFILE 에 환경변수 추가됨${NC}"
else
    echo -e "  ${YELLOW}⚠️ 셸 프로필을 찾지 못했습니다.${NC}"
    echo -e "  아래 내용을 직접 추가해주세요:"
    echo ""
    echo "$ENV_BLOCK"
fi
echo ""

# ============================================================================
# 3. 실행 alias (최적화 플래그)
# ============================================================================

echo -e "${GREEN}[3/3] 실행 alias 설정${NC}"

# alias 블록
ALIAS_BLOCK=$(cat << 'ALIAS_EOF'

# Claude Code 최적화 실행 alias
alias cc='claude'
alias cco='claude --strict-mcp-config --exclude-dynamic-system-prompt-sections'
alias ccw='claude --strict-mcp-config --disable-slash-commands --no-session-persistence --exclude-dynamic-system-prompt-sections'
ALIAS_EOF
)

ALIAS_MARKER="# Claude Code 최적화 실행 alias"

if [ -n "$SHELL_PROFILE" ]; then
    if ! grep -q "$ALIAS_MARKER" "$SHELL_PROFILE" 2>/dev/null; then
        echo "$ALIAS_BLOCK" >> "$SHELL_PROFILE"
        echo -e "  ${GREEN}✅ alias 추가됨:${NC}"
    else
        echo -e "  ${YELLOW}= alias 이미 존재 (스킵)${NC}"
    fi

    echo -e "    ${BLUE}cc${NC}  = claude (기본)"
    echo -e "    ${BLUE}cco${NC} = claude + 최적화 (일반 작업용)"
    echo -e "    ${BLUE}ccw${NC} = claude + 워커 모드 (비대화형, 최대 절약)"
else
    echo -e "  ${YELLOW}⚠️ 셸 프로필에 수동으로 추가해주세요:${NC}"
    echo "$ALIAS_BLOCK"
fi
echo ""

# ============================================================================
# 4. .env.example 에 메모 추가 (프로젝트 레벨)
# ============================================================================

if [ "$GLOBAL_ONLY" = false ]; then
    ENV_EXAMPLE="$PROJECT_DIR/.env.example"

    if [ -f "$ENV_EXAMPLE" ]; then
        if ! grep -q "ENABLE_PROMPT_CACHING_1H" "$ENV_EXAMPLE" 2>/dev/null; then
            cat >> "$ENV_EXAMPLE" << 'ENVEX_EOF'

# ── Claude Code 최적화 (셸 프로필에 설정됨, 참고용) ──
# ENABLE_PROMPT_CACHING_1H=1
# BASH_MAX_OUTPUT_LENGTH=8000
# CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS=8000
# MAX_MCP_OUTPUT_TOKENS=8000
# ENABLE_CLAUDEAI_MCP_SERVERS=false
# CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
ENVEX_EOF
        fi
    fi
fi

# ============================================================================
# 5. CLAUDE.md에 최적화 메모 추가 (프로젝트 레벨)
# ============================================================================

if [ "$GLOBAL_ONLY" = false ]; then
    CLAUDE_MD="$PROJECT_DIR/CLAUDE.md"

    if [ -f "$CLAUDE_MD" ]; then
        OPT_MARKER="## Claude Code 최적화"
        if ! grep -q "$OPT_MARKER" "$CLAUDE_MD" 2>/dev/null; then
            cat >> "$CLAUDE_MD" << 'CMD_EOF'

## Claude Code 최적화

> 이 프로젝트는 토큰 절약을 위해 아래 최적화가 적용되어 있습니다.
> 최초 설정: `bash scripts/setup-claude-optimization.sh`
>
> | 설정 | 위치 | 효과 |
> |------|------|------|
> | `includeGitInstructions: false` | .claude/settings.json | Git 지시어 system prompt 제거 |
> | `autoConnectIde: false` | .claude/settings.json | IDE 자동 연결 해제 |
> | `ENABLE_PROMPT_CACHING_1H=1` | 환경변수 | 캐시 TTL 5분 → 1시간 복원 |
> | `BASH_MAX_OUTPUT_LENGTH=8000` | 환경변수 | bash 출력 토큰 상한 |
> | `cco` alias | 셸 프로필 | `--strict-mcp-config --exclude-dynamic-system-prompt-sections` |
> | `ccw` alias | 셸 프로필 | 워커 모드 (비대화형, 최대 절약) |
CMD_EOF
            echo -e "  ${GREEN}✅ CLAUDE.md에 최적화 메모 추가${NC}"
        fi
    fi
fi

# ============================================================================
# 완료
# ============================================================================

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ 최적화 설정 완료!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "적용하려면: ${YELLOW}source $SHELL_PROFILE${NC}"
echo ""
echo -e "사용법:"
echo -e "  ${BLUE}cc${NC}   → 기본 claude (환경변수 최적화만 적용)"
echo -e "  ${BLUE}cco${NC}  → 일반 작업 (MCP 제한 + 동적 프롬프트 제거)"
echo -e "  ${BLUE}ccw${NC}  → 워커 모드 (비대화형, 최대 토큰 절약)"
echo ""
echo -e "  ${YELLOW}참고: ENABLE_PROMPT_CACHING_1H=1 로 캐시 TTL이${NC}"
echo -e "  ${YELLOW}5분 → 1시간으로 복원됩니다 (v2.1.108+)${NC}"
echo ""

#!/bin/bash
# ============================================================================
# scaffold.sh — 하네스 템플릿 기반 프로젝트 생성기
# ============================================================================
#
# template/ 폴더를 복사하고, 프로젝트에 맞게 설정을 커스터마이징합니다.
#
# 사용법:
#   bash scaffold.sh <프로젝트명> [도메인]
#
# 예시:
#   bash scaffold.sh my-web-app webapp
#   bash scaffold.sh video-factory automation
#   bash scaffold.sh my-api api
#   bash scaffold.sh my-project              # 기본 (general)
#
# 구조:
#   jarvis-harness-kit/
#   ├── scaffold.sh          ← 이 파일
#   ├── template/            ← 하네스 템플릿 (수정하지 말 것)
#   │   ├── CLAUDE.md
#   │   ├── .claude/         ← agents, skills, hooks, commands, rules
#   │   ├── src/             ← Next.js frontend
#   │   ├── backend/         ← FastAPI backend
#   │   └── ...
#   └── GUIDE.md             ← 가이드 문서
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 인자 파싱 ────────────────────────────────────────
PROJECT_NAME="${1:?❌ 사용법: bash scaffold.sh <프로젝트명> [도메인]}"
DOMAIN="${2:-general}"
PROJECT_DIR="$(pwd)/$PROJECT_NAME"

if [ -d "$PROJECT_DIR" ]; then
    echo "❌ 이미 존재하는 디렉토리: $PROJECT_DIR"
    exit 1
fi

# ── 대화형 설정 ─────────────────────────────────────
echo ""
echo "🚀 프로젝트 생성: $PROJECT_NAME (도메인: $DOMAIN)"
echo "   위치: $PROJECT_DIR"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 프로젝트 초기 설정"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 템플릿 선택 ──────────────────────────────────────
echo "0️⃣  템플릿 선택:"
echo ""
echo "   [1] 범용 (universal)         — grill + TDD + diagnose + architecture"
echo "   [2] JARVIS 브라우저 챗봇      — 위 + CDP/WebSocket/LangGraph 도메인 특화"
echo ""
read -p "   선택 [1-2, 기본=1]: " TPL_CHOICE
TPL_CHOICE="${TPL_CHOICE:-1}"

case "$TPL_CHOICE" in
    2) TEMPLATE_DIR="$SCRIPT_DIR/template" ;;
    *) TEMPLATE_DIR="$SCRIPT_DIR/template-universal" ;;
esac

if [ ! -d "$TEMPLATE_DIR" ]; then
    echo "❌ 템플릿 폴더가 없습니다: $TEMPLATE_DIR"
    exit 1
fi
echo "   → $(basename "$TEMPLATE_DIR")"
echo ""

# ── DB 선택 ──────────────────────────────────────────
echo "1️⃣  데이터베이스 선택:"
echo ""
echo "   [1] Supabase (로컬 Docker)  — PostgreSQL + Auth + Realtime"
echo "   [2] Supabase (클라우드)      — 무료 tier, 외부 접근 가능"
echo "   [3] PostgreSQL (직접 설치)   — 순수 PostgreSQL"
echo "   [4] SQLite                  — 파일 기반, 가장 간단"
echo "   [5] 없음                    — DB 설정 나중에"
echo ""
read -p "   선택 [1-5, 기본=5]: " DB_CHOICE
DB_CHOICE="${DB_CHOICE:-5}"

case "$DB_CHOICE" in
    1) DB_TYPE="supabase-local" ;;
    2) DB_TYPE="supabase-cloud" ;;
    3) DB_TYPE="postgresql" ;;
    4) DB_TYPE="sqlite" ;;
    *) DB_TYPE="none" ;;
esac
echo "   → $DB_TYPE"
echo ""

# ── 모니터링 선택 ────────────────────────────────────
echo "2️⃣  에이전트 모니터링:"
echo ""
echo "   [1] agents-observe 플러그인  — 실시간 대시보드 (Docker 필요)"
echo "   [2] Hook 로깅만             — audit.jsonl + HTML 리포트 (기본 내장)"
echo "   [3] 없음"
echo ""
read -p "   선택 [1-3, 기본=2]: " MON_CHOICE
MON_CHOICE="${MON_CHOICE:-2}"

case "$MON_CHOICE" in
    1) MONITORING="agents-observe" ;;
    2) MONITORING="hook-logging" ;;
    *) MONITORING="none" ;;
esac
echo "   → $MONITORING"
echo ""

# ── LLM 선택 ────────────────────────────────────────
echo "3️⃣  로컬 LLM (AI 코드 리뷰용):"
echo ""
echo "   [1] LM Studio (localhost:1234)  — OpenAI 호환 API"
echo "   [2] Ollama (localhost:11434)     — Ollama 네이티브 API"
echo "   [3] 없음 (정적 분석만)"
echo ""
read -p "   선택 [1-3, 기본=1]: " LLM_CHOICE
LLM_CHOICE="${LLM_CHOICE:-1}"

case "$LLM_CHOICE" in
    1) LLM_TYPE="lmstudio" ;;
    2) LLM_TYPE="ollama" ;;
    *) LLM_TYPE="none" ;;
esac
echo "   → $LLM_TYPE"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DB=$DB_TYPE | 모니터링=$MONITORING | LLM=$LLM_TYPE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ============================================================================
# 1. 템플릿 복사
# ============================================================================
echo "📂 템플릿 복사 중..."
cp -r "$TEMPLATE_DIR" "$PROJECT_DIR"
echo "   → $PROJECT_DIR"

# ============================================================================
# 1-b. 도메인별 optional 에이전트 자동 활성화
# ============================================================================
# optional/README.md의 도메인 매핑을 코드화. 활성화 = optional/X.md → agents/X.md 이동.
# 매핑이 없는 도메인은 그대로 둡니다(필요 시 사용자가 수동 이동).
OPTIONAL_DIR="$PROJECT_DIR/.claude/agents/optional"
ACTIVATED_DEVS=()

activate_optional() {
    local dev="$1"
    local src="$OPTIONAL_DIR/${dev}.md"
    local dst="$PROJECT_DIR/.claude/agents/${dev}.md"
    if [ -f "$src" ] && [ ! -f "$dst" ]; then
        mv "$src" "$dst"
        ACTIVATED_DEVS+=("$dev")
    fi
}

if [ -d "$OPTIONAL_DIR" ]; then
    case "$DOMAIN" in
        automation)
            activate_optional browser-dev
            activate_optional automation-dev
            ;;
        video)
            activate_optional integration-dev
            activate_optional automation-dev
            ;;
        youtube)
            activate_optional browser-dev
            activate_optional integration-dev
            activate_optional automation-dev
            ;;
        agent)
            activate_optional integration-dev
            activate_optional automation-dev
            ;;
    esac

    if [ ${#ACTIVATED_DEVS[@]} -gt 0 ]; then
        echo "🧩 도메인 '$DOMAIN' → optional dev 활성화: ${ACTIVATED_DEVS[*]}"
    else
        echo "🧩 도메인 '$DOMAIN' → optional dev 자동 활성화 없음 (.claude/agents/optional/ 에 보관됨, 수동 이동 가능)"
    fi
fi

# ============================================================================
# 2. CLAUDE.md 프로젝트명/도메인 치환
# ============================================================================
echo "📝 CLAUDE.md 커스터마이징..."

if [ "$TPL_CHOICE" = "2" ]; then
    # JARVIS 템플릿
    sed -i.bak "s/# JARVIS Browser Chatbot/# $PROJECT_NAME/" "$PROJECT_DIR/CLAUDE.md"
    sed -i.bak "s/JARVIS Home AI OS의 브라우저 자동화.*/$PROJECT_NAME — 도메인: $DOMAIN, 생성일: $(date +%Y-%m-%d)/" "$PROJECT_DIR/CLAUDE.md"
else
    # 범용 템플릿 — placeholder 치환
    sed -i.bak "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" "$PROJECT_DIR/CLAUDE.md"
    sed -i.bak "s/{{DOMAIN}}/$DOMAIN/g" "$PROJECT_DIR/CLAUDE.md"
    sed -i.bak "s/{{DATE}}/$(date +%Y-%m-%d)/g" "$PROJECT_DIR/CLAUDE.md"
fi

# 의사결정 이력에 설정 추가
cat >> "$PROJECT_DIR/CLAUDE.md" << APPEND

## 초기 설정 (scaffold 생성)
- DB: $DB_TYPE
- 모니터링: $MONITORING
- 로컬 LLM: $LLM_TYPE
APPEND

rm -f "$PROJECT_DIR/CLAUDE.md.bak"

# ============================================================================
# 3. LLM 클라이언트 설정
# ============================================================================
echo "🤖 LLM 클라이언트 설정..."

if [ "$LLM_TYPE" = "ollama" ]; then
    # LM Studio → Ollama로 교체
    cat > "$PROJECT_DIR/.claude/verifier-scripts/llm_client.py" << 'PYEOF'
"""Ollama API 클라이언트 — 검증 Hook 공용 모듈"""
import json, re, sys, requests
from typing import Optional

BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:8b"
TIMEOUT_SECONDS = 25

def ask(prompt, system="", model=DEFAULT_MODEL, temperature=0.1, max_tokens=1024, json_mode=False):
    payload = {"model": model, "prompt": prompt, "system": system, "stream": False,
               "options": {"temperature": temperature, "num_predict": max_tokens, "think": False}}
    if json_mode: payload["format"] = "json"
    try:
        resp = requests.post(f"{BASE_URL}/api/generate", json=payload, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.Timeout: return None
    except requests.RequestException as e:
        print(f"[llm_client] Ollama error: {e}", file=sys.stderr); return None

def ask_json(prompt, system="", model=DEFAULT_MODEL):
    raw = ask(prompt, system, model, json_mode=True)
    if raw is None: return None
    try: return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
        return None

def is_available():
    try: return requests.get(f"{BASE_URL}/api/tags", timeout=3).status_code == 200
    except: return False
PYEOF
    echo "   → Ollama (localhost:11434)"

elif [ "$LLM_TYPE" = "none" ]; then
    cat > "$PROJECT_DIR/.claude/verifier-scripts/llm_client.py" << 'PYEOF'
"""LLM 없음 — 정적 분석만 동작"""
from typing import Optional
BASE_URL = ""
DEFAULT_MODEL = ""

def ask(prompt, system="", model="", **kwargs): return None
def ask_json(prompt, system="", model=""): return None
def is_available(): return False
PYEOF
    echo "   → 없음 (정적 분석만)"

else
    echo "   → LM Studio (기본값 유지)"
fi

# ============================================================================
# 4. DB 설정
# ============================================================================
echo "🗄️  DB 설정..."

if [ "$DB_TYPE" = "supabase-local" ]; then
    mkdir -p "$PROJECT_DIR/supabase"
    cat > "$PROJECT_DIR/supabase/docker-compose.yml" << 'DCYML'
version: "3.8"
services:
  supabase-db:
    image: supabase/postgres:latest
    ports:
      - "54321:5432"
    environment:
      POSTGRES_PASSWORD: your-super-secret-password
      POSTGRES_DB: jarvis
    volumes:
      - supabase-data:/var/lib/postgresql/data
volumes:
  supabase-data:
DCYML
    # .env.example 업데이트
    cat >> "$PROJECT_DIR/.env.example" << 'ENVEOF'

# Supabase (로컬 Docker)
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
DATABASE_URL=postgresql://postgres:your-super-secret-password@localhost:54321/jarvis
ENVEOF
    echo "   → Supabase 로컬 (supabase/docker-compose.yml 생성)"

elif [ "$DB_TYPE" = "supabase-cloud" ]; then
    cat >> "$PROJECT_DIR/.env.example" << 'ENVEOF'

# Supabase (클라우드)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres
ENVEOF
    echo "   → Supabase 클라우드 (.env.example 업데이트)"

elif [ "$DB_TYPE" = "postgresql" ]; then
    cat >> "$PROJECT_DIR/.env.example" << 'ENVEOF'

# PostgreSQL
DATABASE_URL=postgresql://postgres:password@localhost:5432/jarvis
ENVEOF
    echo "   → PostgreSQL (.env.example 업데이트)"

elif [ "$DB_TYPE" = "sqlite" ]; then
    mkdir -p "$PROJECT_DIR/data"
    cat >> "$PROJECT_DIR/.env.example" << 'ENVEOF'

# SQLite
DATABASE_URL=sqlite:///data/jarvis.db
ENVEOF
    echo "   → SQLite (data/ 디렉토리 생성)"

else
    echo "   → 없음 (나중에 설정)"
fi

# ============================================================================
# 5. 모니터링 설정
# ============================================================================
echo "📊 모니터링 설정..."

if [ "$MONITORING" = "agents-observe" ]; then
    cat > "$PROJECT_DIR/.claude/commands/observe-setup.md" << 'MD'
# 에이전트 모니터링 설정

agents-observe 플러그인을 설치하고 대시보드를 시작해줘.

1. Docker Desktop이 실행 중인지 확인
2. 플러그인 설치:
   ```
   /plugin marketplace add simple10/agents-observe
   /plugin install agents-observe@agents-observe
   /reload-plugins
   ```
3. 서버 시작: `/agents-observe:observe start`
4. 상태 확인: `/agents-observe:observe status`
5. 브라우저에서 http://localhost:4981 열기
MD
    echo "   → agents-observe (/observe-setup 커맨드 생성)"

elif [ "$MONITORING" = "none" ]; then
    # Hook 로깅도 제거
    cat > "$PROJECT_DIR/.claude/settings.json" << 'JSON'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/security_gate.py"
          }
        ]
      }
    ]
  }
}
JSON
    echo "   → 없음 (보안 게이트만 유지)"

else
    echo "   → Hook 로깅 (기본값 유지)"
fi

# ============================================================================
# 6. package.json 프로젝트명 치환
# ============================================================================
if [ -f "$PROJECT_DIR/package.json" ]; then
    sed -i.bak "s/\"jarvis-browser-chatbot\"/\"$PROJECT_NAME\"/" "$PROJECT_DIR/package.json"
    rm -f "$PROJECT_DIR/package.json.bak"
fi

# ============================================================================
# 완료
# ============================================================================
echo ""
echo "✅ 프로젝트 생성 완료!"
echo ""

# 파일 수 카운트
FILE_COUNT=$(find "$PROJECT_DIR" -type f | wc -l)
echo "📁 $PROJECT_DIR ($FILE_COUNT 파일)"
echo ""

# 주요 구조만 표시
echo "   .claude/"
echo "   ├── agents/    ($(ls "$PROJECT_DIR/.claude/agents/" 2>/dev/null | wc -l) 에이전트)"
echo "   ├── skills/    ($(ls "$PROJECT_DIR/.claude/skills/" 2>/dev/null | wc -l) 스킬)"
echo "   ├── commands/  ($(ls "$PROJECT_DIR/.claude/commands/" 2>/dev/null | wc -l) 커맨드)"
echo "   ├── hooks/     ($(ls "$PROJECT_DIR/.claude/hooks/" 2>/dev/null | wc -l) Hook)"
echo "   └── rules/     ($(ls "$PROJECT_DIR/.claude/rules/" 2>/dev/null | wc -l) 규칙)"
echo "   src/            Next.js frontend"
echo "   backend/        FastAPI backend"
[ -d "$PROJECT_DIR/supabase" ] && echo "   supabase/        Docker Compose"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 시작하기:"
echo ""
echo "  cd $PROJECT_NAME"

[ "$DB_TYPE" = "supabase-local" ] && echo "" && \
    echo "  # Supabase 로컬 실행" && \
    echo "  cd supabase && docker compose up -d && cd .."

if [ "$LLM_TYPE" = "lmstudio" ]; then
    echo ""
    echo "  # LM Studio 서버 시작 (선택)"
    echo "  #   Local Server 탭 > Start Server (포트 1234)"
elif [ "$LLM_TYPE" = "ollama" ]; then
    echo ""
    echo "  # Ollama 모델 준비 (선택)"
    echo "  ollama pull qwen3:8b"
fi

echo ""
echo "  # Claude Code 시작"
echo "  claude"
echo ""
echo "  # 개발 시작"
echo "  /dev-start              # 현황 파악 + 다음 작업 제안"
echo "  /browser-status         # Chrome 인스턴스 상태"
[ "$MONITORING" = "agents-observe" ] && \
    echo "  /observe-setup          # 모니터링 대시보드 설정"
echo ""
echo "  # 하네스 확장 (선택)"
echo "  /plugin marketplace add revfactory/harness"
echo "  /plugin install harness@harness"
echo "  > 하네스 구성해줘"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

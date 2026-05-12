#!/bin/bash
# launch-chrome.sh — Chrome 디버그 모드 인스턴스 관리
# 사용법: ./launch-chrome.sh [start|stop|status]

set -euo pipefail

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILES_BASE="$HOME/chrome-profiles"

declare -A INSTANCES=(
    ["google"]="9222"
    ["meta"]="9223"
    ["general"]="9224"
)

COMMON_FLAGS=(
    --disable-popup-blocking
    --disable-notifications
    --disable-infobars
    --noerrdialogs
    --no-first-run
    --disable-background-timer-throttling
    --disable-backgrounding-occluded-windows
)

start() {
    for name in "${!INSTANCES[@]}"; do
        local port="${INSTANCES[$name]}"
        local profile="$PROFILES_BASE/$name"

        if curl -s "http://localhost:$port/json/version" > /dev/null 2>&1; then
            echo "✅ $name (포트 $port) — 이미 실행 중"
            continue
        fi

        mkdir -p "$profile"
        "$CHROME" \
            --remote-debugging-port="$port" \
            --user-data-dir="$profile" \
            "${COMMON_FLAGS[@]}" &

        echo "🚀 $name (포트 $port) — 시작됨"
        sleep 1
    done
    echo ""
    echo "💡 처음 실행 시: 각 브라우저 창에서 해당 서비스에 로그인하세요"
    echo "   포트 9222: Google 계정"
    echo "   포트 9223: Meta/Facebook 계정"
    echo "   포트 9224: 기타 서비스"
}

stop() {
    for name in "${!INSTANCES[@]}"; do
        local port="${INSTANCES[$name]}"
        local pids=$(lsof -ti :$port 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "$pids" | xargs kill -SIGTERM 2>/dev/null || true
            echo "🛑 $name (포트 $port) — 중지됨"
        else
            echo "⬜ $name (포트 $port) — 실행 중 아님"
        fi
    done
}

status() {
    for name in "${!INSTANCES[@]}"; do
        local port="${INSTANCES[$name]}"
        if curl -s "http://localhost:$port/json/version" > /dev/null 2>&1; then
            local tabs=$(curl -s "http://localhost:$port/json/list" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
            echo "✅ $name (포트 $port) — 실행 중, 탭 ${tabs}개"
        else
            echo "❌ $name (포트 $port) — 꺼져있음"
        fi
    done
}

case "${1:-status}" in
    start)  start ;;
    stop)   stop ;;
    status) status ;;
    *)      echo "사용법: $0 [start|stop|status]"; exit 1 ;;
esac

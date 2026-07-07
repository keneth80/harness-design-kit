# 하네스 훅 회귀 테스트

킷의 훅 계약(exit 0/2, stdout=경고/stderr=차단 피드백)과 프로파일 구성을 검증한다.
Python 표준 라이브러리(unittest)만 사용 — 새 의존성 없음.

## 실행

```bash
bash tests/run_all.sh
# 또는 개별:
cd tests && python3 -m unittest test_drift_guard -v
```

## 커버리지

| 파일 | 검증 내용 |
|---|---|
| `test_drift_guard.py` | 인터뷰 미완료/미해결 blocking 항목 → 차단(exit 2), frontend(warn_paths) → 경고 강등(exit 0 + 훅 JSON `additionalContext`로 모델 컨텍스트 주입, `permissionDecision` 미포함 검증), mode block/warn/off 3단계, 설정 파일 없음·깨짐·오설정 시 기존 차단 동작 폴백(하위 호환) |
| `test_verify_guard.py` | 의도적 린트 오류 → 경고 발동(exit 0, stdout), 성공 시 침묵, run_on 패턴 필터 |
| `test_secret_scan.py` | 시크릿 탐지 → 차단(exit 2): Supabase service_role JWT(payload 디코딩, anon은 통과), OpenAI/GitHub 키, private key, Edit new_string 스캔. 오탐 방지: placeholder·.env 로컬 파일·lock 파일 제외, .env.example은 스캔 |
| `test_lite_profile.py` | lite settings.json에 은퇴/전환 훅(code_reviewer, backpressure, report_generator) 미등록, full settings에 유지, /commit·/pr-review 파일 부재, switch.sh 왕복·멱등성, 두 템플릿 훅 사본 동일성 |

테스트는 훅을 Claude Code와 동일한 방식(stdin 이벤트 JSON → exit code)으로 직접 호출하므로
결정적이고, 실제 린터 설치 여부에 좌우되지 않는다(린트 오류는 실패하는 명령으로 시뮬레이션).

## 수동 재현 방법

훅 직접 호출:

```bash
# drift_guard 차단 재현 (인터뷰 미완료 도메인)
echo '{"tool_name":"Edit","tool_input":{"file_path":"backend/auth.py"},"cwd":"'$PWD'"}' \
  | python3 .claude/hooks/drift_guard.py; echo "exit=$?"

# verify_guard 발동 재현
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/foo.py"},"cwd":"'$PWD'"}' \
  | python3 .claude/hooks/verify_guard.py
```

headless(claude -p)로 재현하려면 스캐폴딩된 프로젝트에서:

```bash
# 인터뷰 미완료 도메인 수정 시도 → drift-guard 차단 메시지 확인
claude -p "backend/auth.py 파일에 주석 한 줄만 추가해줘" --permission-mode acceptEdits

# lite 프로파일에서 코드 수정 → code_reviewer 자동 발동이 없는지 확인
# (수정 직후 verify_guard 경고 외 리뷰 출력이 없어야 정상)
```

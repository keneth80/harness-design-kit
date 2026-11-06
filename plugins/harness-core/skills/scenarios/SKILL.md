---
name: scenarios
description: 완성품을 실제로 켜서 확인하는 시나리오 검사(harness.scenarios.json)를 만들고 돌린다. 명령이나 HTTP 요청으로 "그러면 이렇게 된다"를 확인하고, 앞 시나리오가 실패하면 뒤는 blocked로, 되돌리기 어려운 작업은 위험과 복구 확인을 함께 적는다. 원장에 묶으면 루프의 통과 기준이 된다.
when_to_use: 시나리오 만들기, 배포 확인, 배포 검증, 스모크 테스트, 동작 확인 시나리오, 헬스체크, 실제로 켜서 확인, 마이그레이션 확인, 인수 기준.
argument-hint: "[만들기 | 실행 | 태그]"
---

# 시나리오 검사

단위 테스트가 부품 검사라면 시나리오는 완성품을 켜 보는 검사입니다. "빌드가 된다 → 홈이 열린다 → 없는 주소는 404"처럼
사람이 정한 결과를 순서대로 확인합니다. 앞 단계가 실패하면 뒤 단계는 돌리지 않고 `blocked`로 남깁니다.

## 실행

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scenario_run.py"               # 전부
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scenario_run.py" --only deploy # id나 태그로 (needs도 함께)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scenario_run.py" --list        # 순서와 의존만
```

상태: `pass`, `fail`, `blocked`(앞 시나리오 실패), `skipped`(필요한 환경변수 없음). 선택한 것이 모두 pass여야 통과입니다.
실패한 시나리오에 `risk`가 있으면 영향, 복구 방법, 복구 확인 결과(`recoveryChecks`)를 함께 보여줍니다.
**복구 방법은 실행하지 않습니다.** 사용자에게 보여주고, 실행할지는 사용자가 정합니다.

## 만들기

`harness.scenarios.json`이 없으면 `${CLAUDE_PLUGIN_ROOT}/templates/harness.scenarios.json`을 출발점으로 쓴다.

1. **출처를 먼저 읽는다:** `docs/spec.md`의 인수 기준, README의 실행·배포 방법, package.json 등의 스크립트, 라우트 목록.
2. **시나리오마다 한 문장(`then`)과 확인 방법(`check`) 하나.** 확인은 관찰 가능한 것만 쓴다.
   - `command`: `run`, `expect.exit`(기본 0), `expect.contains`(출력에 있어야 할 문자열), `timeout`
   - `http`: `url`, `method`, `headers`, `body`, `expect.status`(기본 200), `expect.contains`, `timeout`
3. **순서는 `needs`로.** 서버가 떠야 API를 확인할 수 있으면 API 시나리오의 needs에 서버 시나리오를 넣는다. 순환은 오류다.
4. **환경마다 다른 값은 `${변수}`로.** `BASE_URL`, `PROD_URL`처럼 쓰고 값은 환경변수로 준다. 토큰도 `${API_TOKEN}`처럼만 쓴다.
   값이 없으면 그 시나리오는 `skipped`이고 통과로 치지 않는다. 파일에 실제 비밀값을 쓰지 않는다.
5. **되돌리기 어려운 작업(배포, 마이그레이션, 결제 설정)에는 `risk`:** `impact`(무엇이 깨지나), `recovery`(사람이 할 복구),
   `recoveryChecks`(복구가 필요한지 판단할 읽기 전용 시나리오 id).
6. **태그로 묶는다:** 로컬에서 늘 돌릴 것은 `local`, 배포 뒤에만 의미 있는 것은 `deploy`.
7. 사용자에게 시나리오 목록(`--list`)을 보여주고 확인을 받는다. 이 파일은 검증 기준이라서 이후 에이전트가 고치면 확인 창이 뜬다.

## 원장에 묶기

`harness.config.json`의 verify에 `"scenarios": ["local"]`(태그·id 목록) 또는 `true`(전부)를 넣으면
`verify_run.py`, backpressure, fix-until-green, `/harness-core:goal`이 시나리오까지 통과해야 pass로 봅니다.
배포 뒤 확인처럼 매번 돌릴 필요가 없는 것은 원장에 묶지 말고 `--only deploy`로 따로 돌리세요.

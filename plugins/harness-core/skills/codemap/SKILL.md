---
name: codemap
description: 코드를 정적 파싱해 각 파일의 공개 API(export)와 로컬 import를 정리한 docs/codemap.md를 지금 바로 다시 만든다. 평소엔 작업 종료 시 자동 갱신되고 세션 시작 때 자동으로 읽힌다.
when_to_use: 코드맵 만들어줘, 코드 구조 지도, codemap 갱신, 처음 보는 저장소 구조 파악.
disable-model-invocation: true
---

# 코드맵 생성

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/codemap.py" "$PWD"
```

- Python, JS/TS(.js .jsx .ts .tsx)를 지원한다. 함수 본문의 호출 관계나 의미는 담지 않는다(코드와 어긋날 위험 때문).
- 생성된 `docs/codemap.md`는 직접 고치지 않는다.
- init된 프로젝트에서는 Stop 훅이 소스가 바뀔 때마다 자동 갱신하고, SessionStart 훅이 다음 세션에 읽힌다.
- 끄려면 `harness.config.json`에 `"codemap": {"enabled": false}`.

---
name: task-routing
trigger: "라우팅|라우터|의도|intent|LangGraph|서비스 분류|파이프라인|그래프"
---

# Task Routing Skill

LangGraph StateGraph 기반 의도 파악 및 서비스 라우팅 지식.

## LangGraph 라우터 설계

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class RouterState(TypedDict):
    message: str              # 사용자 입력
    user_id: str              # 가족 구성원 ID
    intent: str               # 파악된 의도
    service: str              # 대상 서비스 (google, meta, general)
    port: int                 # Chrome CDP 포트
    task_params: dict         # 태스크에 전달할 파라미터
    task_result: Any          # 실행 결과
    error: str | None         # 에러 메시지
    ws_session_id: str        # WebSocket 세션 (실시간 스트리밍용)

graph = StateGraph(RouterState)
graph.add_node("parse_intent", parse_intent)
graph.add_node("route_service", route_service)
graph.add_node("execute_task", execute_task)
graph.add_node("format_response", format_response)
graph.add_node("handle_error", handle_error)
graph.add_node("notify_telegram", notify_telegram)

graph.set_entry_point("parse_intent")
graph.add_edge("parse_intent", "route_service")
graph.add_conditional_edges("route_service", check_service_available,
    {"available": "execute_task", "unavailable": "handle_error"})
graph.add_edge("execute_task", "format_response")
graph.add_edge("format_response", "notify_telegram")
graph.add_edge("notify_telegram", END)
graph.add_edge("handle_error", "notify_telegram")
```

## 의도 분류 패턴

| 키워드 패턴 | intent | service | port |
|-------------|--------|---------|------|
| 구글시트, 스프레드시트, sheets | google_sheets | google | 9222 |
| 지메일, 메일, gmail | gmail | google | 9222 |
| 메타, 비즈니스, 인스타, 페이스북, DM, 댓글 | meta_business | meta | 9223 |
| 네이버, 쿠팡, 검색 | general_browse | general | 9224 |

LLM 의도 파악이 실패하면 키워드 기반 폴백 사용.

## 에러 처리 전략

```python
async def execute_task(state: RouterState) -> RouterState:
    try:
        # 실행 전 WebSocket으로 "task_start" 전송
        await ws_manager.send(state["ws_session_id"], {
            "type": "task_start",
            "payload": {"service": state["service"]}
        })

        result = await task_registry.execute(
            state["intent"], state["service"], state["task_params"]
        )
        state["task_result"] = result

    except CDPConnectionError:
        state["error"] = f"{state['service']} Chrome 연결 실패. 브라우저가 실행 중인지 확인하세요."
    except SessionExpiredError:
        state["error"] = f"{state['service']} 로그인 세션 만료. 재로그인이 필요합니다."
    except Exception as e:
        state["error"] = f"작업 실행 중 오류: {str(e)}"

    return state
```

# WebSocket 메시지 포맷 규칙

모든 WebSocket 메시지는 반드시 아래 포맷을 준수해야 합니다:

```typescript
{
  type: string,          // 메시지 타입 (chat_send, task_start, task_progress 등)
  payload: object,       // 데이터
  userId: string,        // 가족 구성원 ID
  timestamp: string      // ISO 8601
}
```

Python 백엔드에서도 동일한 구조를 사용합니다:

```python
message = {
    "type": "task_progress",
    "payload": {"taskId": task_id, "step": step_name},
    "userId": user_id,
    "timestamp": datetime.now(timezone.utc).isoformat(),
}
```

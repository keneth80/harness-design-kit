// === WebSocket 메시지 타입 ===

export interface WSMessage {
  type: WSMessageType;
  payload: Record<string, unknown>;
  userId: string;
  timestamp: string;
}

export type WSMessageType =
  | "chat_send"
  | "chat_response"
  | "task_start"
  | "task_progress"
  | "task_complete"
  | "task_error"
  | "service_status";

// === 채팅 ===

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  taskId?: string;
  screenshot?: string;
}

// === 태스크 ===

export interface TaskProgress {
  taskId: string;
  service: string;
  steps: TaskStep[];
  currentStep: number;
}

export interface TaskStep {
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  screenshot?: string;
}

// === 사용자 ===

export interface User {
  id: string;
  name: string;
  role: "admin" | "user";
}

// === 서비스 상태 ===

export interface ServiceStatus {
  name: string;
  port: number;
  connected: boolean;
  tabCount?: number;
}

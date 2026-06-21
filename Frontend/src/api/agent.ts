const BASE_URL = "http://localhost:8000";

export interface AgentHistory {
  id: string;
  chat_id: string;
  user_id: string;
  agent_stage: string;
  stage_name: string;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  status: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface ToolExecution {
  id: string;
  chat_id: string;
  agent_id: string;
  tool_name: string;
  tool_input: Record<string, any>;
  tool_output: Record<string, any>;
  status: string;
  error_message?: string;
  screenshot_url?: string;
  created_at: string;
}

export interface AgentStatus {
  chat_id: string;
  current_stage: string | null;
  stage_name: string | null;
  status: string;
  error_message?: string;
  updated_at: string | null;
}

export const agentApi = {
  async getHistory(chatId: string): Promise<AgentHistory[]> {
    const response = await fetch(`${BASE_URL}/sciparser/v1/agent/history/${chatId}`);
    const data = await response.json();
    return data.history;
  },

  async getTools(chatId: string): Promise<ToolExecution[]> {
    const response = await fetch(`${BASE_URL}/sciparser/v1/agent/tools/${chatId}`);
    const data = await response.json();
    return data.tools;
  },

  async getStatus(chatId: string): Promise<AgentStatus> {
    const response = await fetch(`${BASE_URL}/sciparser/v1/agent/status/${chatId}`);
    return response.json();
  },

  connectWebSocket(chatId: string, onMessage: (data: any) => void) {
    const ws = new WebSocket(`${BASE_URL.replace('http', 'ws')}/sciparser/v1/agent/stream/${chatId}`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };
    return ws;
  }
};
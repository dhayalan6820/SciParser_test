import React from 'react';

interface AgentStageViewProps {
  chatId: string;
  isVisible: boolean;
  agentHistory: any[];
  currentStatus: any;
  error: string | null;
}

export function AgentStageView({ chatId, isVisible, agentHistory, currentStatus, error }: AgentStageViewProps) {
  if (!isVisible) return null;

  return (
    <div className="fixed right-0 top-0 h-full w-80 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 overflow-y-auto p-4 z-50">
      <h2 className="text-xl font-bold mb-4 text-gray-900 dark:text-gray-100">Agent Execution View</h2>

      {error && (
        <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/30 rounded text-red-800 dark:text-red-200 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <h3 className="font-semibold text-gray-700 dark:text-gray-300">Agent Stages</h3>
        {agentHistory.length === 0 ? (
          <div className="text-center py-6 text-sm text-gray-500">
            No agent execution history yet
          </div>
        ) : (
          agentHistory.map((stage, index) => (
            <div
              key={stage.id || `stage-${stage.agent_stage}-${index}`}
              className={`
                relative p-4 rounded-lg border-2 transition-all duration-300
                ${currentStatus?.agent_stage === stage.agent_stage && currentStatus?.status === 'IN_PROGRESS' 
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' 
                  : ''}
                ${stage.status === 'COMPLETED' 
                  ? 'border-green-500 bg-green-50 dark:bg-green-900/20' 
                  : ''}
                ${stage.status === 'FAILED' 
                  ? 'border-red-500 bg-red-50 dark:bg-red-900/20' 
                  : ''}
                ${!currentStatus?.agent_stage && !stage.status 
                  ? 'border-gray-200 dark:border-gray-700' 
                  : ''}
              `}
            >
              <div className="flex items-center gap-3 mb-3">
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm
                  ${currentStatus?.agent_stage === stage.agent_stage && currentStatus?.status === 'IN_PROGRESS' 
                    ? 'bg-blue-500 text-white' 
                    : ''}
                  ${stage.status === 'COMPLETED' 
                    ? 'bg-green-500 text-white' 
                    : ''}
                  ${stage.status === 'FAILED' 
                    ? 'bg-red-500 text-white' 
                    : ''}
                  ${!currentStatus?.agent_stage && !stage.status 
                    ? 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300' 
                    : ''}
                `}>
                  {stage.agent_stage.replace('AGENT_', '')}
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100">{stage.stage_name}</h3>
                  <span className={`
                    text-xs px-2 py-1 rounded-full
                    ${currentStatus?.agent_stage === stage.agent_stage && currentStatus?.status === 'IN_PROGRESS' 
                      ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' 
                      : ''}
                    ${stage.status === 'COMPLETED' 
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' 
                      : ''}
                    ${stage.status === 'FAILED' 
                      ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' 
                      : ''}
                    ${!currentStatus?.agent_stage && !stage.status 
                      ? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300' 
                      : ''}
                  `}>
                    {stage.status}
                  </span>
                </div>
              </div>

              {stage.error_message && (
                <div className="mt-2 p-2 bg-red-100 dark:bg-red-900/30 rounded text-red-800 dark:text-red-200 text-sm">
                  <strong>Error:</strong> {stage.error_message}
                </div>
              )}

              <div className="mt-3 text-xs text-gray-500 dark:text-gray-400">
                <div className="mb-1">
                  <strong>Input:</strong>
                  <pre className="mt-1 bg-gray-100 dark:bg-gray-800 p-2 rounded overflow-x-auto">
                    {JSON.stringify(stage.input_data, null, 2)}
                  </pre>
                </div>
                <div>
                  <strong>Output:</strong>
                  <pre className="mt-1 bg-gray-100 dark:bg-gray-800 p-2 rounded overflow-x-auto">
                    {JSON.stringify(stage.output_data, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
import React from 'react';

interface AgentStageCardProps {
  stage: any;
  isActive: boolean;
  isCompleted: boolean;
  isFailed: boolean;
}

export function AgentStageCard({ stage, isActive, isCompleted, isFailed }: AgentStageCardProps) {
  return (
    <div className={`
      relative p-4 rounded-lg border-2 transition-all duration-300
      ${isActive ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : ''}
      ${isCompleted ? 'border-green-500 bg-green-50 dark:bg-green-900/20' : ''}
      ${isFailed ? 'border-red-500 bg-red-50 dark:bg-red-900/20' : ''}
      ${!isActive && !isCompleted && !isFailed ? 'border-gray-200 dark:border-gray-700' : ''}
    `}>
      <div className="flex items-center gap-3 mb-3">
        <div className={`
          w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm
          ${isActive ? 'bg-blue-500 text-white' : ''}
          ${isCompleted ? 'bg-green-500 text-white' : ''}
          ${isFailed ? 'bg-red-500 text-white' : ''}
          ${!isActive && !isCompleted && !isFailed ? 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300' : ''}
        `}>
          {stage.agent_stage.replace('AGENT_', '')}
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">{stage.stage_name}</h3>
          <span className={`
            text-xs px-2 py-1 rounded-full
            ${isActive ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' : ''}
            ${isCompleted ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : ''}
            ${isFailed ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' : ''}
            ${!isActive && !isCompleted && !isFailed ? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300' : ''}
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
        <div>Input: {JSON.stringify(stage.input_data)}</div>
        <div>Output: {JSON.stringify(stage.output_data)}</div>
      </div>
    </div>
  );
}
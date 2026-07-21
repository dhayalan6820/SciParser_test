import * as React from "react";
import { Panel } from "./shared";
import { Button } from "../button";
import { Input } from "../input";
import { sciparserApi, AdminLLMConfig } from "../../../api";
import { toast } from "../toast-notifications";
import { Bot, Save, RotateCcw } from "lucide-react";
import { motion } from "framer-motion";

export const LLMConfigTab: React.FC = () => {
  const [config, setConfig] = React.useState<AdminLLMConfig | null>(null);
  const [activeConfig, setActiveConfig] = React.useState<AdminLLMConfig | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isSaving, setIsSaving] = React.useState(false);

  const fetchConfig = async () => {
    setIsLoading(true);
    try {
      const data = await sciparserApi.adminGetLLMConfig();
      setConfig(data);
      setActiveConfig(data);
    } catch (error: any) {
      toast("error", "Error loading config", error.message);
    } finally {
      setIsLoading(false);
    }
  };

  React.useEffect(() => {
    fetchConfig();
  }, []);

  const handleChange = (field: keyof AdminLLMConfig, value: string | number) => {
    if (config) {
      setConfig({ ...config, [field]: value });
    }
  };

  const handleSave = async () => {
    if (!config) return;
    setIsSaving(true);
    try {
      await sciparserApi.adminSetLLMConfig({
        model_name: config.model_name,
        input_cost: Number(config.input_cost),
        output_cost: Number(config.output_cost),
        context_window: Number(config.context_window),
      });
      toast("success", "Saved", "Main LLM configuration has been applied.");
      await fetchConfig(); // Refresh
    } catch (error: any) {
      toast("error", "Save failed", error.message);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading || !config) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-500">
        <Bot className="h-6 w-6 animate-pulse mr-2" /> Loading configuration...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
          <Bot className="h-6 w-6 text-indigo-500" />
          LLM Model Settings
        </h2>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Configure the primary LLM model used across the application and update its cost properties.
        </p>
      </div>

      {activeConfig && (
        <div className="bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 rounded-lg p-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-indigo-900 dark:text-indigo-300">Currently Active Model</h3>
            <p className="text-xs text-indigo-700 dark:text-indigo-400 mt-1">
              {activeConfig.model_name} (Input: ${activeConfig.input_cost}/1M, Output: ${activeConfig.output_cost}/1M, Context: {activeConfig.context_window})
            </p>
          </div>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-500/20">
            <Bot className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
          </div>
        </div>
      )}

      <Panel title="Main Model Configuration">
        <div className="space-y-4 pt-2">
            
          <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Model Name</label>
              <Input
                value={config.model_name}
                onChange={(e) => handleChange("model_name", e.target.value)}
                placeholder="e.g. gpt-4o, claude-3-5-sonnet"
              />
              <p className="text-xs text-zinc-500">The exact identifier for OpenRouter or your LLM provider.</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Input Cost (per 1M tokens)</label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-zinc-500 text-sm">$</span>
                  <Input
                    type="number"
                    step="0.001"
                    className="pl-7"
                    value={config.input_cost}
                    onChange={(e) => handleChange("input_cost", e.target.value)}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Output Cost (per 1M tokens)</label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-zinc-500 text-sm">$</span>
                  <Input
                    type="number"
                    step="0.001"
                    className="pl-7"
                    value={config.output_cost}
                    onChange={(e) => handleChange("output_cost", e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Context Window Size</label>
              <Input
                type="number"
                value={config.context_window}
                onChange={(e) => handleChange("context_window", e.target.value)}
                placeholder="e.g. 128000"
              />
              <p className="text-xs text-zinc-500">The maximum number of tokens allowed per request.</p>
            </div>

            <div className="pt-4 flex justify-end gap-3 border-t border-zinc-100 dark:border-zinc-800">
            <Button 
              variant="default"
              onClick={handleSave} 
              disabled={isSaving}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              {isSaving ? (
                <Bot className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Save Configuration
            </Button>
          </div>

        </div>
      </Panel>
    </div>
  );
};

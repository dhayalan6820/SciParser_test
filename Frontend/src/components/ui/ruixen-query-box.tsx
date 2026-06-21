"use client";

import { Mic, SendHorizonal, Upload, CheckCircle2, FileText, AlertCircle } from "lucide-react";
import { useState, useRef } from "react";
import { cn } from "../../../lib/utils";
import { Textarea } from "./textarea";
import { useAutoResizeTextarea } from "../../hooks/use-auto-resize-textarea";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { Button } from "./button";

interface RuixenQueryBoxProps {
  onSendMessage?: (text: string) => void;
  onFileUploaded?: (fileName: string, fileSize: number, fileType: string) => void;
}

export default function RuixenQueryBox({ onSendMessage, onFileUploaded }: RuixenQueryBoxProps) {
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({
    minHeight: 56,
    maxHeight: 220,
  });

  const [inputValue, setInputValue] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleSend = () => {
    if (!inputValue.trim()) return;
    
    if (onSendMessage) {
      onSendMessage(inputValue);
    } else {
      console.log("Submitted:", inputValue);
    }
    
    setInputValue("");
    adjustHeight(true);
  };

  const handleFileUpload = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    
    const file = files[0];
    console.log("Uploaded file:", file);
    
    if (onFileUploaded) {
      onFileUploaded(file.name, file.size, file.type || "application/pdf");
    }
    
    setUploadStatus({
      type: "success",
      text: `"${file.name}" ready to analyze`,
    });
    
    setTimeout(() => {
      setUploadStatus(null);
    }, 4000);
  };

  const toggleRecording = () => {
    if (isRecording) {
      setIsRecording(false);
      // Simulate speech-to-text text insertion
      const simulatedText = "How do I extract citations from the downloaded paper?";
      setInputValue((prev) => (prev.length > 0 ? prev + " " + simulatedText : simulatedText));
      setTimeout(() => adjustHeight(), 50);
    } else {
      setIsRecording(true);
      setUploadStatus(null);
    }
  };

  return (
    <div className="w-full px-2 sm:px-4 py-4">
      {uploadStatus && (
        <div className={cn(
          "max-w-2xl mx-auto mb-3 flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-medium border animate-in fade-in slide-in-from-top-2 duration-300",
          uploadStatus.type === "success" 
            ? "bg-emerald-50/90 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-100 dark:border-emerald-900/60"
            : "bg-rose-50 dark:bg-rose-955/20 text-rose-700 dark:text-rose-400 border-rose-100 dark:border-rose-900/70"
        )}>
          {uploadStatus.type === "success" ? <CheckCircle2 className="size-4 text-emerald-500" /> : <AlertCircle className="size-4 text-rose-500" />}
          <span>{uploadStatus.text}</span>
        </div>
      )}

      {isRecording && (
        <div className="max-w-2xl mx-auto mb-3 flex items-center justify-between px-4 py-2 rounded-xl bg-indigo-50/90 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900/50 text-xs text-indigo-700 dark:text-indigo-400 font-semibold animate-pulse">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-indigo-600 dark:bg-indigo-400 animate-ping"></span>
            Listening and acquiring audio context...
          </div>
          <button 
            onClick={() => setIsRecording(false)}
            className="text-[10px] uppercase font-bold text-slate-500 dark:text-slate-400 hover:text-indigo-600 hover:underline cursor-pointer border-0 bg-transparent"
          >
            Cancel
          </button>
        </div>
      )}

      <div
        className="relative max-w-2xl mx-auto rounded-3xl border border-slate-200 dark:border-slate-800 shadow-lg overflow-hidden transition-all duration-300 focus-within:shadow-xl focus-within:border-slate-300 dark:focus-within:border-slate-700 bg-slate-50 dark:bg-slate-900"
        style={{
          backgroundImage: "var(--ruixen-bg)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        {/* Subtle decorative glow */}
        <div className="absolute inset-0 bg-slate-950/20 pointer-events-none dark:block hidden"></div>

        <div className="relative z-10 flex flex-col">
          <Textarea
            id="ai-textarea"
            ref={textareaRef}
            placeholder="Ask SciParser anything..."
            className={cn(
              "w-full resize-none border-none bg-transparent",
              "text-base text-slate-800 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-300/80",
              "px-5 pt-5 pb-16 rounded-2xl leading-[1.5]",
              "focus-visible:ring-0 focus-visible:ring-offset-0 focus:outline-none"
            )}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              adjustHeight();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />

          {/* Action Row */}
          <div className="absolute bottom-3 right-3 flex items-center gap-2 z-20">
            <button
              type="button"
              onClick={toggleRecording}
              className={cn(
                "p-2.5 rounded-full transition-all duration-300 select-none cursor-pointer",
                isRecording 
                  ? "bg-rose-500 hover:bg-rose-600 text-white animate-bounce" 
                  : "bg-slate-100 dark:bg-slate-100/10 hover:bg-slate-200 dark:hover:bg-slate-100/20 text-slate-650 dark:text-white border border-slate-200/60 dark:border-white/10"
              )}
              title={isRecording ? "Stop recording and translate speech" : "Simulate Speech-to-text"}
            >
              <Mic className="w-4 h-4" />
            </button>

            {/* File Upload Popover */}
            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="p-2.5 rounded-full bg-slate-100 dark:bg-slate-100/10 hover:bg-slate-200 dark:hover:bg-slate-100/20 text-slate-650 dark:text-white border border-slate-200/60 dark:border-white/10 transition-colors cursor-pointer"
                  title="Upload scientific document"
                >
                  <Upload className="w-4 h-4" />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-64 p-4 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-100 rounded-xl shadow-xl z-50">
                <div className="text-xs space-y-3">
                  <div className="flex items-center gap-1.5 font-bold text-slate-900 dark:text-white uppercase tracking-wider text-[10px]">
                    <FileText className="size-3.5 text-indigo-500" />
                    Upload Scientific Document
                  </div>
                  <p className="text-slate-500 dark:text-slate-400 leading-relaxed text-[11px]">
                    Select PDF, TXT, or JSON files to feed contextual metadata directly into SciParser.
                  </p>
                  
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.txt,.json,.csv"
                    ref={fileInputRef}
                    onChange={(e) => handleFileUpload(e.target.files)}
                    className="hidden"
                  />
                  
                  <div 
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-lg p-4 text-center cursor-pointer hover:border-indigo-500 dark:hover:border-indigo-500 hover:bg-slate-50 dark:hover:bg-slate-900/40 transition-all duration-200"
                  >
                    <Upload className="size-5 mx-auto text-slate-400 dark:text-slate-500 mb-1.5" />
                    <span className="font-semibold block text-[10.5px]">Click or Drop File</span>
                    <span className="text-[9.5px] text-slate-400 block mt-0.5">PDF up to 50MB</span>
                  </div>

                  <Button
                    size="sm"
                    className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg text-xs"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Choose Document
                  </Button>
                </div>
              </PopoverContent>
            </Popover>

            <button
              type="button"
              onClick={handleSend}
              disabled={!inputValue.trim()}
              className={cn(
                "p-2.5 rounded-full transition-all duration-300 cursor-pointer border border-transparent shadow-sm",
                inputValue.trim()
                  ? "bg-indigo-600 dark:bg-white text-white dark:text-indigo-950 hover:scale-105"
                  : "bg-slate-100 dark:bg-slate-100/5 text-slate-400 dark:text-white/40 cursor-not-allowed"
              )}
            >
              <SendHorizonal className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        :root, html {
          --ruixen-bg: linear-gradient(135deg, #ffffff 0%, #f1f5f9 100%);
        }
        
        .dark, [data-theme="dark"] {
          --ruixen-bg: url('https://pub-940ccf6255b54fa799a9b01050e6c227.r2.dev/ruixen_chat_gradient.png');
        }
      ` }} />
    </div>
  );
}

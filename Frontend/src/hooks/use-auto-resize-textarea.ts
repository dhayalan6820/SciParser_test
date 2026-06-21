import { useRef, useCallback, useEffect } from 'react';

interface UseAutoResizeTextareaProps {
  minHeight?: number;
  maxHeight?: number;
}

export function useAutoResizeTextarea({
  minHeight = 56,
  maxHeight = 220,
}: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback((reset = false) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    if (reset) {
      textarea.style.height = `${minHeight}px`;
      return;
    }

    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = 'auto';
    
    // Calculate new height based on scrollHeight
    const newHeight = Math.min(
      Math.max(textarea.scrollHeight, minHeight),
      maxHeight
    );
    
    textarea.style.height = `${newHeight}px`;
  }, [minHeight, maxHeight]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const handleInput = () => adjustHeight();
    const handleResize = () => adjustHeight();

    textarea.addEventListener('input', handleInput);
    window.addEventListener('resize', handleResize);

    return () => {
      textarea.removeEventListener('input', handleInput);
      window.removeEventListener('resize', handleResize);
    };
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}
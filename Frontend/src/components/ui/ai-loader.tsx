import * as React from "react";

interface LoaderProps {
  size?: number; 
  text?: string;
}

export const Component: React.FC<LoaderProps> = ({ size = 180, text = "Generating" }) => {
  const letters = text.split("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gradient-to-b from-slate-100 via-slate-200 to-slate-350 dark:from-[#1a3379] dark:via-[#0f172a] dark:to-black bg-opacity-95 backdrop-blur-sm transition-all duration-300">
      <div
        className="relative flex items-center justify-center font-sans select-none"
        style={{ width: size, height: size }}
      >
        <div className="flex gap-0.5 z-10">
          {letters.map((letter, index) => (
            <span
              key={index}
              className="inline-block text-slate-800 dark:text-white opacity-40 animate-loaderLetter font-extrabold text-base tracking-wide"
              style={{ animationDelay: `${index * 0.08}s` }}
            >
              {letter}
            </span>
          ))}
        </div>

        <div
          className="absolute inset-0 rounded-full animate-loaderCircle"
        ></div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes loaderCircle {
          0% {
            transform: rotate(90deg);
            box-shadow:
              0 6px 12px 0 #38bdf8 inset,
              0 12px 18px 0 #005dff inset,
              0 36px 36px 0 #1e40af inset,
              0 0 3px 1.2px rgba(56, 189, 248, 0.3),
              0 0 6px 1.8px rgba(0, 93, 255, 0.2);
          }
          50% {
            transform: rotate(270deg);
            box-shadow:
              0 6px 12px 0 #60a5fa inset,
              0 12px 6px 0 #0284c7 inset,
              0 24px 36px 0 #005dff inset,
              0 0 3px 1.2px rgba(56, 189, 248, 0.3),
              0 0 6px 1.8px rgba(0, 93, 255, 0.2);
          }
          100% {
            transform: rotate(450deg);
            box-shadow:
              0 6px 12px 0 #4dc8fd inset,
              0 12px 18px 0 #005dff inset,
              0 36px 36px 0 #1e40af inset,
              0 0 3px 1.2px rgba(56, 189, 248, 0.3),
              0 0 6px 1.8px rgba(0, 93, 255, 0.2);
          }
        }

        @keyframes loaderLetter {
          0%,
          100% {
            opacity: 0.4;
            transform: translateY(0);
          }
          20% {
            opacity: 1;
            transform: scale(1.18) translateY(-2px);
          }
          40% {
            opacity: 0.7;
            transform: translateY(0);
          }
        }

        .animate-loaderCircle {
          animation: loaderCircle 4s linear infinite;
        }

        .animate-loaderLetter {
          animation: loaderLetter 2.4s infinite;
        }

        /* Override circle colors safely for light/dark mode */
        html.dark .animate-loaderCircle,
        [data-theme="dark"] .animate-loaderCircle {
          animation: loaderCircle 4s linear infinite;
        }

        html:not(.dark) .animate-loaderCircle,
        [data-theme="light"] .animate-loaderCircle {
          box-shadow:
            0 6px 12px 0 #94a3b8 inset,
            0 12px 18px 0 #475569 inset,
            0 36px 36px 0 #1e293b inset,
            0 0 3px 1.2px rgba(148, 163, 184, 0.4),
            0 0 6px 1.8px rgba(71, 85, 105, 0.3);
        }
      ` }} />
    </div>
  );
};

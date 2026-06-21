import {
  motion,
  AnimatePresence,
  type Variants,
} from "framer-motion";

const customBezier = [0.43, 0.13, 0.23, 0.96] as const;

const containerVariants: Variants = {
  hidden: {
    opacity: 0,
    y: 30,
  },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.7,
      ease: customBezier,
      delayChildren: 0.1,
      staggerChildren: 0.1,
    },
  },
};

const itemVariants: Variants = {
  hidden: {
    opacity: 0,
    y: 20,
  },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.6,
      ease: customBezier,
    },
  },
};

const numberVariants = {
  hidden: (direction: number) => ({
    opacity: 0,
    x: direction * 40,
    y: 15,
    rotate: direction * 5,
  }),
  visible: {
    opacity: 0.7,
    x: 0,
    y: 0,
    rotate: 0,
    transition: {
      duration: 0.8,
      ease: customBezier,
    },
  },
};

const ghostVariants: Variants = {
  hidden: {
    scale: 0.8,
    opacity: 0,
    y: 15,
    rotate: -5,
  },

  visible: {
    scale: 1,
    opacity: 1,
    y: 0,
    rotate: 0,
    transition: {
      duration: 0.6,
      ease: customBezier,
    },
  },

  hover: {
    scale: 1.1,
    y: -10,
    rotate: [0, -5, 5, -5, 0],
    transition: {
      duration: 0.8,
      ease: customBezier,
      rotate: {
        duration: 2,
        ease: customBezier,
        repeat: Infinity,
        repeatType: "reverse" as const,
      },
    },
  },

  floating: {
    y: [-5, 5],
    transition: {
      y: {
        duration: 2,
        ease: customBezier,
        repeat: Infinity,
        repeatType: "reverse" as const,
      },
    },
  },
};

interface NotFoundProps {
  onGoBack?: () => void;
}

export function NotFound({ onGoBack }: NotFoundProps) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-white dark:bg-slate-950 px-4">
      <AnimatePresence mode="wait">
        <motion.div
          className="text-center"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          exit="hidden"
        >
          <div className="flex items-center justify-center gap-4 md:gap-6 mb-8 md:mb-12">
            <motion.span
              className="text-[80px] md:text-[120px] font-bold text-slate-800 dark:text-slate-200 opacity-70 font-signika select-none"
              variants={numberVariants}
              custom={-1}
            >
              4
            </motion.span>

            <motion.div
              variants={ghostVariants}
              initial="hidden"
              animate={["visible", "floating"]}
              whileHover="hover"
            >
              <img
                src="https://xubohuah.github.io/xubohua.top/Group.png"
                alt="Ghost"
                className="w-[80px] h-[80px] md:w-[120px] md:h-[120px] object-contain select-none"
                draggable={false}
                referrerPolicy="no-referrer"
              />
            </motion.div>

            <motion.span
              className="text-[80px] md:text-[120px] font-bold text-slate-800 dark:text-slate-200 opacity-70 font-signika select-none"
              variants={numberVariants}
              custom={1}
            >
              4
            </motion.span>
          </div>

          <motion.h1
            className="text-3xl md:text-5xl font-bold text-[#222222] dark:text-slate-100 mb-4 md:mb-6 opacity-70 font-dm-sans select-none"
            variants={itemVariants}
          >
            Boo! Page missing!
          </motion.h1>

          <motion.p
            className="text-lg md:text-xl text-[#222222] dark:text-slate-400 mb-8 md:mb-12 opacity-50 font-dm-sans select-none"
            variants={itemVariants}
          >
            Whoops! This page must be a ghost - it's not here!
          </motion.p>

          <motion.div
            variants={itemVariants}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
            whileHover={{
              scale: 1.05,
              transition: {
                duration: 0.3,
                ease: customBezier,
              },
            }}
          >
            {onGoBack ? (
              <button
                type="button"
                onClick={onGoBack}
                className="inline-block bg-[#222222] dark:bg-slate-100 text-white dark:text-slate-900 px-8 py-3 rounded-full text-lg font-medium hover:bg-black dark:hover:bg-white transition-colors font-dm-sans select-none cursor-pointer border-0"
              >
                Back to SciParser Gateway
              </button>
            ) : (
              <a
                href="/"
                className="inline-block bg-[#222222] dark:bg-slate-100 text-white dark:text-slate-900 px-8 py-3 rounded-full text-lg font-medium hover:bg-black dark:hover:bg-white transition-colors font-dm-sans select-none cursor-pointer"
              >
                Find shelter
              </a>
            )}
          </motion.div>

          <motion.div
            className="mt-12"
            variants={itemVariants}
          >
            <a
              href="#"
              className="text-[#222222] dark:text-slate-400 opacity-50 hover:opacity-70 transition-opacity underline text-sm font-dm-sans select-none"
            >
              What is 404?
            </a>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
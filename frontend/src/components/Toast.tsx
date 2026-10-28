import React, { createContext, useContext, useState, useCallback } from "react";
import { CheckCircle, AlertCircle, Info, X } from "lucide-react";
import { Toast as ToastSurface } from "./ui";

export type ToastType = "success" | "error" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const showToast = useCallback((message: string, type: ToastType = "info") => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => {
          const IconMap = {
            success: CheckCircle,
            error: AlertCircle,
            info: Info,
          };
          const Icon = IconMap[toast.type];

          return (
            <ToastSurface
              key={toast.id}
              role={toast.type === "error" ? "alert" : "status"}
              aria-live="polite"
              className={`ui-toast--${toast.type} pointer-events-auto flex items-start gap-3 p-3.5 transition-transform duration-200`}
            >
              <Icon className="w-4 h-4 mt-0.5 shrink-0" />
              <p className="text-xs font-medium leading-relaxed flex-1">{toast.message}</p>
              <button
                onClick={() => removeToast(toast.id)}
                className="min-h-11 min-w-11 -mr-2 -mt-2 inline-flex items-center justify-center rounded-pill text-secondary hover:bg-stone-100 hover:text-stone-900 shrink-0"
                aria-label="Dismiss notification"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </ToastSurface>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    return {
      showToast: (msg: string) => console.log(msg),
    };
  }
  return context;
};

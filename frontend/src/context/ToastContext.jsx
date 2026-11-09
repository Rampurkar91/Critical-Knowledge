import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';

const ToastContext = createContext(null);

const TONES = {
  success: { Icon: CheckCircle2, classes: 'border-emerald-200 bg-emerald-50 text-emerald-800' },
  error: { Icon: XCircle, classes: 'border-rose-200 bg-rose-50 text-rose-800' },
  warning: { Icon: AlertTriangle, classes: 'border-amber-200 bg-amber-50 text-amber-800' },
  info: { Icon: Info, classes: 'border-navy-200 bg-navy-50 text-navy-800' },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const dismiss = useCallback((id) => setToasts((items) => items.filter((item) => item.id !== id)), []);
  const notify = useCallback((message, tone = 'info') => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setToasts((items) => [...items.slice(-3), { id, message, tone }]);
    window.setTimeout(() => dismiss(id), 5200);
  }, [dismiss]);
  const value = useMemo(() => ({ notify, dismiss }), [notify, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-[100] flex w-[min(92vw,380px)] flex-col gap-2">
        {toasts.map((toast) => {
          const { Icon, classes } = TONES[toast.tone] || TONES.info;
          return (
            <div key={toast.id} className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-3.5 py-3 shadow-panel fade-in ${classes}`}>
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <p className="flex-1 text-sm font-medium leading-relaxed">{toast.message}</p>
              <button onClick={() => dismiss(toast.id)} className="rounded p-0.5 opacity-60 hover:opacity-100" aria-label="Dismiss">
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

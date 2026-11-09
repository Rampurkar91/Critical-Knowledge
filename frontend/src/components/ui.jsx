import { AlertCircle, Check, Clock3, FileQuestion, Inbox, ShieldAlert, X } from 'lucide-react';

export const cn = (...parts) => parts.filter(Boolean).join(' ');

export function Card({ className = '', children, ...props }) {
  return <div className={cn('card', className)} {...props}>{children}</div>;
}

export function SectionHeader({ title, subtitle, action, icon: Icon }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        {Icon && <span className="mt-0.5 rounded-xl bg-teal-50 p-2 text-teal-700"><Icon className="h-4 w-4" /></span>}
        <div>
          <h2 className="section-title">{title}</h2>
          {subtitle && <p className="muted mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

const BADGE_TONES = {
  teal: 'bg-teal-50 text-teal-700 ring-1 ring-teal-200',
  navy: 'bg-navy-50 text-navy-700 ring-1 ring-navy-200',
  slate: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
  green: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200',
  rose: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200',
  violet: 'bg-violet-50 text-violet-700 ring-1 ring-violet-200',
};

export function Badge({ tone = 'slate', children, className = '' }) {
  return <span className={cn('badge', BADGE_TONES[tone] || BADGE_TONES.slate, className)}>{children}</span>;
}

export function statusTone(status) {
  return ({
    Verified: 'green', approved: 'green', shared: 'teal', completed: 'green', done: 'green',
    'Needs Review': 'amber', pending: 'amber', draft: 'slate', open: 'amber', in_progress: 'navy',
    Conflicting: 'rose', rejected: 'rose', blocked: 'rose',
    Unsupported: 'violet', Outdated: 'slate', acknowledged: 'teal',
  })[status] || 'slate';
}

export function StatusPill({ status, label }) {
  return <Badge tone={statusTone(status)}>{label || status || 'unknown'}</Badge>;
}

export function SensitivityPill({ label, level }) {
  const tone = level >= 3 ? 'rose' : level === 2 ? 'violet' : level === 1 ? 'navy' : 'green';
  return <Badge tone={tone}><ShieldAlert className="h-3 w-3" />{label || level}</Badge>;
}

export function StatCard({ icon: Icon, label, value, hint, tone = 'teal' }) {
  const toneClasses = {
    teal: 'bg-teal-50 text-teal-700', navy: 'bg-navy-50 text-navy-700',
    amber: 'bg-amber-50 text-amber-700', rose: 'bg-rose-50 text-rose-700',
    violet: 'bg-violet-50 text-violet-700',
  };
  return (
    <Card className="p-4 fade-in">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-navy-950">{value ?? '—'}</p>
          {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
        </div>
        {Icon && <span className={cn('rounded-xl p-2.5', toneClasses[tone])}><Icon className="h-5 w-5" /></span>}
      </div>
    </Card>
  );
}

export function Loading({ label = 'Loading authorised knowledge…' }) {
  return (
    <div className="flex min-h-[240px] items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-slate-500">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-teal-600" />
        <p className="text-sm font-medium">{label}</p>
      </div>
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, description, action }) {
  return (
    <Card className="flex min-h-[220px] flex-col items-center justify-center p-8 text-center">
      <span className="rounded-2xl bg-slate-100 p-3 text-slate-500"><Icon className="h-6 w-6" /></span>
      <h3 className="mt-4 font-bold text-navy-900">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}

export function ErrorPanel({ error, onRetry }) {
  return (
    <Card className="border-rose-200 bg-rose-50/70 p-5">
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 text-rose-600" />
        <div className="flex-1">
          <h3 className="font-bold text-rose-800">Could not load this view</h3>
          <p className="mt-1 text-sm text-rose-700">{error?.message || 'An unexpected error occurred.'}</p>
          {onRetry && <button className="btn-outline mt-3" onClick={onRetry}>Try again</button>}
        </div>
      </div>
    </Card>
  );
}

export function Modal({ open, onClose, title, children, footer, wide = false }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-950/50 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <div className={cn('card max-h-[88vh] w-full overflow-hidden fade-in', wide ? 'max-w-4xl' : 'max-w-xl')} onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h3 className="font-bold text-navy-900">{title}</h3>
          <button className="btn-ghost !p-2" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        <div className="max-h-[68vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50/70 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function Drawer({ open, onClose, title, subtitle, children, wide = false }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-navy-950/40 backdrop-blur-[2px]" onMouseDown={onClose}>
      <aside className={cn('h-full overflow-y-auto bg-white shadow-2xl fade-in', wide ? 'w-[min(94vw,760px)]' : 'w-[min(94vw,480px)]')} onMouseDown={(e) => e.stopPropagation()}>
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white/95 px-5 py-4 backdrop-blur">
          <div>
            <h3 className="font-bold text-navy-900">{title}</h3>
            {subtitle && <p className="muted mt-0.5">{subtitle}</p>}
          </div>
          <button className="btn-ghost !p-2" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        <div className="px-5 py-5">{children}</div>
      </aside>
    </div>
  );
}

export function ProgressBar({ value = 0, tone = 'teal' }) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div className={cn('h-full rounded-full transition-all', tone === 'teal' ? 'bg-teal-500' : 'bg-navy-600')} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function EvidenceList({ items = [], emptyLabel = 'No supporting evidence is linked.' }) {
  if (!items?.length) {
    return <div className="flex items-center gap-2 rounded-xl bg-violet-50 px-3 py-2 text-sm text-violet-700"><FileQuestion className="h-4 w-4" />{emptyLabel}</div>;
  }
  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={item.evidence_id || item.id || index} className="rounded-xl border border-slate-200 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-bold text-navy-800">{item.source_title || item.source_ref || item.source_id}</span>
            <span className="chip">chars {item.start_char}–{item.end_char}</span>
          </div>
          <p className="evidence-quote">{item.quote}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500">
            <span>{item.source_ref || item.source_id}</span>
            <span>•</span><span>{item.source_type || 'source'}</span>
            {item.sensitivity && <><span>•</span><span>{item.sensitivity}</span></>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ScoreRationale({ items = [] }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-1.5 text-xs text-slate-600">
      {items.map((item, index) => (
        <li key={index} className="flex gap-2"><Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" /><span>{item}</span></li>
      ))}
    </ul>
  );
}

export function KeyValue({ items = [] }) {
  return (
    <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {items.filter(Boolean).map(({ label, value }) => (
        <div key={label} className="rounded-xl bg-slate-50 px-3 py-2">
          <dt className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</dt>
          <dd className="mt-1 text-sm font-medium text-navy-900">{value ?? '—'}</dd>
        </div>
      ))}
    </dl>
  );
}

export function DemoBanner({ compact = false }) {
  return (
    <div className={cn('flex items-center gap-2 rounded-xl border border-teal-200 bg-teal-50/80 text-teal-800', compact ? 'px-3 py-2 text-xs' : 'px-4 py-3 text-sm')}>
      <ShieldAlert className="h-4 w-4 shrink-0" />
      <span><strong>Demonstration data.</strong> Synthetic Atlas Migration records; no real documents or secrets.</span>
    </div>
  );
}

export function formatDate(value, withTime = false) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}) });
}

export function truncate(value, length = 120) {
  const text = String(value || '');
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

export function scoreTone(score) {
  if (score >= 75) return 'green';
  if (score >= 50) return 'amber';
  return 'rose';
}

export function timeAgo(value) {
  if (!value) return '—';
  const date = new Date(value);
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}

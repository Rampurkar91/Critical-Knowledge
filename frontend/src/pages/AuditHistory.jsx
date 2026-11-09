import { useMemo, useState } from 'react';
import { ScrollText, ShieldCheck, Link2 } from 'lucide-react';
import { api, projectPath } from '../lib/api';
import { useApiData } from '../lib/useApi';
import { useProject } from '../context/ProjectContext';
import { Badge, Card, EmptyState, ErrorPanel, Loading, SectionHeader, StatusPill, formatDate } from '../components/ui';

export default function AuditHistory() {
  const { projectId } = useProject();
  const [action, setAction] = useState('all');
  const [outcome, setOutcome] = useState('all');
  const query = useApiData(() => api.get(projectPath(projectId, '/audit')), [projectId], { enabled: Boolean(projectId) });
  const items = useMemo(() => (query.data?.items || []).filter((item) => (action === 'all' || item.action === action) && (outcome === 'all' || item.outcome === outcome)), [query.data, action, outcome]);
  const actions = useMemo(() => [...new Set((query.data?.items || []).map((item) => item.action))].sort(), [query.data]);
  if (!projectId) return <EmptyState title="No project selected" description="Select a project to inspect audit history." />;
  if (query.loading && !query.data) return <Loading />;
  if (query.error) return <ErrorPanel error={query.error} onRetry={query.refresh} />;
  return (
    <div className="space-y-6 fade-in">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">Audit history</p><h2 className="mt-1 text-2xl font-extrabold tracking-tight text-navy-950">Append-only shared-information trail</h2><p className="muted mt-1">Ingestion, extraction, review, approval, sharing, exports, denials and acknowledgements are recorded.</p></div><div className="flex flex-wrap gap-2"><select className="input !w-auto !py-2" value={action} onChange={(e) => setAction(e.target.value)}><option value="all">All actions</option>{actions.map((item) => <option key={item}>{item}</option>)}</select><select className="input !w-auto !py-2" value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="all">All outcomes</option>{['allowed','denied','blocked','duplicate'].map((item) => <option key={item}>{item}</option>)}</select></div></div>
      <Card className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><SectionHeader title={`${items.length} audit events`} subtitle="Newest events first." icon={ScrollText} /><div className="flex items-center gap-2"><Badge tone={query.data.hash_chain_continuity_valid ? 'green' : 'rose'}><Link2 className="h-3 w-3" /> {query.data.hash_chain_continuity_valid ? 'hash-chain continuity valid' : 'chain issue detected'}</Badge></div></div><p className="text-xs text-slate-500">{query.data.chain_check}</p></Card>
      <Card className="overflow-hidden"><div className="overflow-x-auto"><table className="w-full min-w-[1000px] border-collapse"><thead><tr className="table-head"><th className="px-4 py-3">Time</th><th className="px-4 py-3">Actor</th><th className="px-4 py-3">Action</th><th className="px-4 py-3">Outcome</th><th className="px-4 py-3">Resource</th><th className="px-4 py-3">Details</th><th className="px-4 py-3">Hash</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} className="hover:bg-slate-50/60"><td className="table-cell whitespace-nowrap text-xs">{formatDate(item.created_at, true)}</td><td className="table-cell text-xs">{item.actor_email}</td><td className="table-cell"><Badge tone="navy">{item.action}</Badge></td><td className="table-cell"><StatusPill status={item.outcome} label={item.outcome} /></td><td className="table-cell text-xs">{item.resource_type}<br /><span className="text-slate-400">{item.resource_id}</span></td><td className="table-cell"><pre className="max-w-[360px] overflow-auto rounded-lg bg-slate-50 p-2 text-[10px] text-slate-600">{JSON.stringify(item.details, null, 2)}</pre></td><td className="table-cell"><span className="font-mono text-[10px] text-slate-400">{item.event_hash.slice(0, 12)}…</span></td></tr>)}</tbody></table>{!items.length && <div className="p-5"><EmptyState icon={ShieldCheck} title="No audit events match" description="Adjust the filters or perform an action in the workflow." /></div>}</div></Card>
    </div>
  );
}

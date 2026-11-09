import { useMemo, useState } from 'react';
import { GitBranch, ArrowRight, UserRound, CalendarDays } from 'lucide-react';
import { api, projectPath } from '../lib/api';
import { useApiData } from '../lib/useApi';
import { useProject } from '../context/ProjectContext';
import { Badge, Card, Drawer, EmptyState, ErrorPanel, EvidenceList, Loading, SectionHeader, StatusPill, formatDate } from '../components/ui';

export default function DecisionHistory() {
  const { projectId } = useProject();
  const [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const query = useApiData(() => api.get(projectPath(projectId, '/decisions')), [projectId], { enabled: Boolean(projectId) });
  const items = useMemo(() => (query.data?.items || []).filter((item) => filter === 'all' || item.verification_status === filter), [query.data, filter]);
  if (!projectId) return <EmptyState title="No project selected" description="Select a project to inspect decision history." />;
  if (query.loading && !query.data) return <Loading />;
  if (query.error) return <ErrorPanel error={query.error} onRetry={query.refresh} />;
  return (
    <div className="space-y-6 fade-in">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">Decision reconstruction</p><h2 className="mt-1 text-2xl font-extrabold tracking-tight text-navy-950">Historical decisions and their reasons</h2><p className="muted mt-1">Each decision is linked to owners, dependencies, evidence and any superseding decision.</p></div><select className="input !w-auto !py-2" value={filter} onChange={(e) => setFilter(e.target.value)}><option value="all">All statuses</option>{['Verified','Needs Review','Conflicting','Unsupported','Outdated'].map((s) => <option key={s}>{s}</option>)}</select></div>
      <Card className="p-5"><SectionHeader title={`${items.length} authorised decisions`} subtitle="Ordered by recorded source date." icon={GitBranch} />
        <div className="relative space-y-4 before:absolute before:bottom-2 before:left-[15px] before:top-2 before:w-px before:bg-slate-200">
          {items.map((decision) => (
            <button key={decision.id} className="relative flex w-full gap-4 rounded-xl border border-slate-200 p-4 text-left transition hover:border-teal-300 hover:bg-teal-50/30" onClick={() => setSelected(decision)}>
              <span className="relative z-10 mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-teal-100 text-teal-700"><GitBranch className="h-4 w-4" /></span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-start justify-between gap-2"><div className="flex flex-wrap gap-2"><Badge tone="navy">{decision.external_ref}</Badge><StatusPill status={decision.verification_status} /></div><span className="flex items-center gap-1 text-[11px] text-slate-400"><CalendarDays className="h-3 w-3" />{formatDate(decision.source_timestamp)}</span></div>
                <p className="mt-2 text-sm font-semibold leading-relaxed text-navy-900">{decision.statement}</p>
                {decision.why && <p className="mt-1.5 text-xs text-slate-500"><strong>Why:</strong> {decision.why}</p>}
                <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500"><span className="chip"><UserRound className="h-3 w-3" />{decision.owner || 'Unassigned'}</span><span className="chip">{decision.evidence?.length || 0} evidence spans</span>{decision.supersedes && <span className="chip">supersedes {decision.supersedes}</span>}{decision.superseded_by && <Badge tone="slate">superseded by {decision.superseded_by}</Badge>}{decision.dependencies?.length > 0 && <span className="chip">depends on {decision.dependencies.join(', ')}</span>}<span className="chip">heuristic {decision.reliability_score}</span></div>
              </div><ArrowRight className="mt-2 h-4 w-4 shrink-0 text-slate-300" />
            </button>
          ))}
          {!items.length && <EmptyState title="No decisions match" description="Try another status filter or sign in with an authorised role." />}
        </div>
      </Card>
      <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.external_ref || 'Decision'} subtitle={selected ? `${selected.verification_status} · ${formatDate(selected.source_timestamp)}` : ''} wide>
        {selected && <div className="space-y-5"><div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-sm font-semibold leading-relaxed text-navy-900">{selected.statement}</p><p className="mt-2 text-sm text-slate-600"><strong>Why:</strong> {selected.why || 'No rationale recorded.'}</p></div><div><h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">Original evidence</h4><EvidenceList items={selected.evidence} /></div><div><h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">Explainable heuristic score</h4><ul className="space-y-1.5 text-xs text-slate-600">{selected.score_rationale?.map((line, index) => <li key={index}>• {line}</li>)}</ul></div></div>}
      </Drawer>
    </div>
  );
}

import { useState } from 'react';
import { GitCompareArrows, Clock3, ShieldCheck } from 'lucide-react';
import { api, projectPath } from '../lib/api';
import { useApiData } from '../lib/useApi';
import { useProject } from '../context/ProjectContext';
import { useToast } from '../context/ToastContext';
import { Badge, Card, EmptyState, ErrorPanel, EvidenceList, Loading, SectionHeader, StatusPill, formatDate } from '../components/ui';

export default function ConflictDashboard() {
  const { projectId, can } = useProject();
  const { notify } = useToast();
  const [resolving, setResolving] = useState(null);
  const [form, setForm] = useState({ resolution_claim_id: '', note: '' });
  const conflicts = useApiData(() => api.get(projectPath(projectId, '/conflicts')), [projectId], { enabled: Boolean(projectId) });
  const outdated = useApiData(() => api.get(projectPath(projectId, '/outdated')), [projectId], { enabled: Boolean(projectId) });
  const openResolve = (conflict) => { setResolving(conflict); setForm({ resolution_claim_id: conflict.claim_a_id, note: '' }); };
  const resolve = async (event) => { event.preventDefault(); try { await api.post(`/api/conflicts/${resolving.id}/resolve`, { ...form, note: form.note || 'Manager selected the authoritative record after source review.' }); notify('Conflict resolved; selected claim requires re-approval.', 'success'); setResolving(null); conflicts.refresh(); outdated.refresh(); } catch (e) { notify(e.message, 'error'); } };
  if (!projectId) return <EmptyState title="No project selected" description="Select a project to inspect contradictions." />;
  if (conflicts.loading && !conflicts.data) return <Loading />;
  if (conflicts.error) return <ErrorPanel error={conflicts.error} onRetry={conflicts.refresh} />;
  return (
    <div className="space-y-6 fade-in">
      <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">Conflict & freshness detection</p><h2 className="mt-1 text-2xl font-extrabold tracking-tight text-navy-950">Contradictions stay visible until a human resolves them</h2><p className="muted mt-1">Conflicts are detected from differing recorded values on the same key. Outdated records come from explicit supersession.</p></div>
      <Card className="p-5"><SectionHeader title={`${conflicts.data.total} contradiction records`} subtitle="Both sides retain exact source evidence." icon={GitCompareArrows} />
        <div className="space-y-4">{conflicts.data.items.map((conflict) => <div key={conflict.id} className="rounded-2xl border border-slate-200 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><Badge tone="rose">{conflict.conflict_type.replaceAll('_',' ')}</Badge><StatusPill status={conflict.status} /></div><h3 className="mt-2 font-mono text-sm font-bold text-navy-900">{conflict.normalized_key}</h3><p className="mt-1 text-xs text-slate-500">{conflict.rationale}</p></div>{conflict.status === 'open' && can('review.approve') && <button className="btn-outline" onClick={() => openResolve(conflict)}>Resolve</button>}</div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">{[['Record A', conflict.value_a, conflict.claim_a], ['Record B', conflict.value_b, conflict.claim_b]].map(([label, value, claim]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p><p className="mt-1 font-semibold text-navy-900">{value}</p><p className="mt-1 text-[11px] text-slate-500">{claim?.external_ref} · {formatDate(claim?.source_timestamp)} · {claim?.verification_status}</p><div className="mt-2"><EvidenceList items={claim?.evidence || []} /></div></div>)}</div>
          {conflict.status === 'resolved' && <p className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-800">Resolved: {conflict.resolution_note}</p>}
        </div>)}{!conflicts.data.items.length && <EmptyState title="No visible conflicts" description="No contradictory records are visible for this role and clearance." />}</div>
      </Card>
      <Card className="p-5"><SectionHeader title={`${outdated.data?.total || 0} outdated records`} subtitle="Older records remain auditable but are excluded from handovers." icon={Clock3} /><div className="space-y-2">{(outdated.data?.items || []).map((claim) => <div key={claim.id} className="rounded-xl border border-slate-200 p-3"><div className="flex flex-wrap justify-between gap-2"><p className="text-sm font-semibold text-navy-900">{claim.external_ref} · {claim.statement}</p><StatusPill status={claim.verification_status} /></div><p className="mt-1 text-xs text-slate-500">Superseded by {claim.superseded_by || 'a newer approved record'} · {formatDate(claim.source_timestamp)}</p></div>)}</div></Card>
      {resolving && <div className="fixed inset-0 z-50 grid place-items-center bg-navy-950/50 p-4" onMouseDown={() => setResolving(null)}><form className="card w-full max-w-lg p-5 fade-in" onMouseDown={(e) => e.stopPropagation()} onSubmit={resolve}><SectionHeader title="Resolve contradiction" subtitle="Select the authoritative claim. The other record is marked Outdated." icon={ShieldCheck} /><label className="label">Authoritative claim</label><select className="input" value={form.resolution_claim_id} onChange={(e) => setForm({ ...form, resolution_claim_id: e.target.value })}><option value={resolving.claim_a_id}>{resolving.claim_a?.external_ref || 'Record A'} · {resolving.value_a}</option><option value={resolving.claim_b_id}>{resolving.claim_b?.external_ref || 'Record B'} · {resolving.value_b}</option></select><label className="label mt-4">Resolution note</label><textarea className="input" rows="3" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="Why is this source authoritative?" required minLength={3} /><div className="mt-5 flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={() => setResolving(null)}>Cancel</button><button className="btn-primary">Resolve conflict</button></div></form></div>}
    </div>
  );
}

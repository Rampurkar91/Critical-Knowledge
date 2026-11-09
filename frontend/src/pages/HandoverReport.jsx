import { useEffect, useState } from 'react';
import { CheckCircle2, Download, FileText, PencilLine, Send, ShieldCheck, Sparkles } from 'lucide-react';
import { api, projectPath } from '../lib/api';
import { useApiData } from '../lib/useApi';
import { useProject } from '../context/ProjectContext';
import { useToast } from '../context/ToastContext';
import { Badge, Card, EmptyState, ErrorPanel, EvidenceList, Loading, Modal, SectionHeader, StatusPill, formatDate } from '../components/ui';

const safe = async (promise) => { try { return await promise; } catch { return null; } };

export default function HandoverReport() {
  const { projectId, can, isManager } = useProject();
  const { notify } = useToast();
  const [selectedId, setSelectedId] = useState('');
  const [recipient, setRecipient] = useState('');
  const [editOpen, setEditOpen] = useState(false);
  const [editJson, setEditJson] = useState('{}');
  const [editTitle, setEditTitle] = useState('');
  const [editNote, setEditNote] = useState('');
  const [busy, setBusy] = useState('');
  const list = useApiData(() => api.get(projectPath(projectId, '/handovers')), [projectId], { enabled: Boolean(projectId) });
  const members = useApiData(() => safe(api.get(projectPath(projectId, '/members'))), [projectId], { enabled: Boolean(projectId) });
  const detail = useApiData(() => api.get(`/api/handovers/${selectedId}`), [selectedId], { enabled: Boolean(selectedId) });

  useEffect(() => { if (!selectedId && list.data?.items?.length) setSelectedId(list.data.items[0].id); }, [list.data, selectedId]);
  useEffect(() => { if (detail.data?.content) { setEditJson(JSON.stringify(detail.data.content, null, 2)); setEditTitle(detail.data.title); } }, [detail.data]);
  useEffect(() => { if (members.data?.length && !recipient) setRecipient(members.data.find((m) => m.role === 'incoming_engineer')?.user_id || members.data[0]?.user_id || ''); }, [members.data, recipient]);

  const withBusy = async (name, fn, message) => { setBusy(name); try { const result = await fn(); notify(message || `${name} completed.`, 'success'); list.refresh(); detail.refresh(); return result; } catch (e) { notify(e.message, 'error'); return null; } finally { setBusy(''); } };
  const generate = async (event) => { event.preventDefault(); if (!recipient) return notify('Choose a recipient.', 'warning'); const result = await withBusy('generate', () => api.post(projectPath(projectId, '/handovers/generate'), { recipient_user_id: recipient }), 'Draft handover generated from approved evidence.'); if (result?.id) setSelectedId(result.id); };
  const approve = () => withBusy('approve', () => api.post(`/api/handovers/${selectedId}/approve`, {}), 'Handover approved for controlled sharing.');
  const share = () => withBusy('share', () => api.post(`/api/handovers/${selectedId}/share`, {}), 'Handover shared with the recipient.');
  const exportReport = async () => { try { await api.download(`/api/handovers/${selectedId}/export`, `knowledgebridge-${selectedId}.md`); notify('Permission-filtered Markdown export downloaded.', 'success'); } catch (e) { notify(e.message, 'error'); } };
  const saveEdit = async () => { let parsed; try { parsed = JSON.parse(editJson); } catch { return notify('Edited content must be valid JSON.', 'error'); } const result = await withBusy('edit', () => api.patch(`/api/handovers/${selectedId}`, { content_json: parsed, title: editTitle, edit_note: editNote || 'Manager correction before approval' }), 'Handover correction saved.'); if (result) { setEditOpen(false); setEditNote(''); } };

  if (!projectId) return <EmptyState title="No project selected" description="Select a project to generate a handover." />;
  if (list.loading && !list.data) return <Loading />;
  if (list.error) return <ErrorPanel error={list.error} onRetry={list.refresh} />;
  const handovers = list.data.items || [];
  const selected = handovers.find((item) => item.id === selectedId);
  const content = detail.data?.content;

  return (
    <div className="space-y-6 fade-in">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">Innovation 3 · Adaptive handover</p><h2 className="mt-1 text-2xl font-extrabold tracking-tight text-navy-950">Review, correct, approve and share</h2><p className="muted mt-1">Generation applies the recipient's clearance before retrieving any claim. Drafts are not visible to recipients.</p></div><div className="flex gap-2"><button className="btn-outline" disabled={!selectedId} onClick={exportReport}><Download className="h-4 w-4" /> Export</button></div></div>

      {can('handover.generate') && <Card className="p-5"><SectionHeader title="Generate role-specific handover" subtitle="Only approved, verified, authorised claims are used." icon={Sparkles} /><form onSubmit={generate} className="flex flex-wrap items-end gap-3"><div className="min-w-[260px] flex-1"><label className="label">Recipient</label><select className="input" value={recipient} onChange={(e) => setRecipient(e.target.value)}><option value="">Choose an incoming member</option>{(members.data || []).map((member) => <option key={member.id} value={member.user_id}>{member.full_name} · {member.role_label} · {member.clearance_label}</option>)}</select></div><button className="btn-primary" disabled={Boolean(busy)}>{busy === 'generate' ? 'Generating…' : 'Generate draft'}</button></form></Card>}

      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <Card className="p-4"><SectionHeader title={`Handovers (${handovers.length})`} icon={FileText} /><div className="space-y-2">{handovers.map((item) => <button key={item.id} className={`w-full rounded-xl border p-3 text-left transition ${item.id === selectedId ? 'border-teal-400 bg-teal-50/60' : 'border-slate-200 hover:bg-slate-50'}`} onClick={() => setSelectedId(item.id)}><div className="flex items-center justify-between gap-2"><StatusPill status={item.status} /><Badge tone="slate">{item.clearance}</Badge></div><p className="mt-2 text-sm font-bold text-navy-900">{item.title}</p><p className="mt-1 text-[11px] text-slate-500">{item.recipient_role.replaceAll('_',' ')} · v{item.version} · {formatDate(item.generated_at, true)}</p></button>)}{!handovers.length && <EmptyState title="No handovers yet" description="Generate a draft after approving reconstructed claims." />}</div></Card>
        <div className="space-y-5">
          {selected && <Card className="p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-xl font-extrabold text-navy-950">{selected.title}</h3><p className="muted mt-1">{selected.recipient_role.replaceAll('_',' ')} · {selected.clearance} clearance · version {selected.version}</p></div><div className="flex flex-wrap gap-2"><StatusPill status={selected.status} />{selected.approved_at && <Badge tone="green">approved {formatDate(selected.approved_at)}</Badge>}{selected.shared_at && <Badge tone="teal">shared {formatDate(selected.shared_at)}</Badge>}</div></div><div className="mt-4 flex flex-wrap gap-2">{isManager && <button className="btn-outline" onClick={() => setEditOpen(true)}><PencilLine className="h-4 w-4" /> Review / correct</button>}{isManager && selected.status === 'draft' && <button className="btn-outline" disabled={Boolean(busy)} onClick={approve}><CheckCircle2 className="h-4 w-4" /> {busy === 'approve' ? 'Approving…' : 'Approve'}</button>}{isManager && ['approved','shared','acknowledged','in_progress','completed'].includes(selected.status) && <button className="btn-primary" disabled={Boolean(busy)} onClick={share}><Send className="h-4 w-4" /> {busy === 'share' ? 'Sharing…' : 'Share with recipient'}</button>}</div><p className="mt-3 text-xs text-slate-500">Applied filters: review_status=approved, verification_status=Verified, max_clearance={detail.data?.clearance_level ?? selected.clearance_level}, claim-type allowlist, role scope.</p></Card>}
          {detail.loading && <Loading label="Loading permission-filtered report…" />}
          {detail.error && <ErrorPanel error={detail.error} onRetry={detail.refresh} />}
          {content && <div className="space-y-5">
            <Card className="p-5"><SectionHeader title="Next five important actions" subtitle="Priority-based continuation plan." icon={Sparkles} /><div className="space-y-2">{content.next_actions?.map((action, index) => <div key={action.external_ref || index} className="rounded-xl border border-slate-200 p-3"><div className="flex items-start gap-3"><span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-teal-100 text-xs font-bold text-teal-800">{index + 1}</span><div><p className="text-sm font-semibold text-navy-900">{action.statement}</p><p className="mt-1 text-[11px] text-slate-500">{action.external_ref} · priority {action.priority} · {action.evidence?.length || 0} evidence span(s)</p></div></div></div>)}</div></Card>
            <div className="grid gap-5 lg:grid-cols-2"><Card className="p-5"><SectionHeader title="Responsibilities" icon={FileText} /><div className="space-y-2">{content.responsibilities?.map((task) => <div key={task.external_ref || task.task_id} className="rounded-xl bg-slate-50 p-3"><p className="text-sm font-semibold text-navy-900">{task.external_ref} · {task.title}</p><p className="mt-1 text-[11px] text-slate-500">{task.status} · priority {task.priority} · due {formatDate(task.due_date)} · deps {task.dependencies?.join(', ') || 'none'}</p></div>)}</div></Card><Card className="p-5"><SectionHeader title="Key decisions" icon={ShieldCheck} /><div className="space-y-2">{content.key_decisions?.map((decision) => <div key={decision.external_ref} className="rounded-xl bg-slate-50 p-3"><p className="text-sm font-semibold text-navy-900">{decision.external_ref} · {decision.statement}</p>{decision.rationale && <p className="mt-1 text-xs text-slate-500">Why: {decision.rationale}</p>}</div>)}</div></Card></div>
            <Card className="p-5"><SectionHeader title="Evidence register" subtitle="Exact source quotes and character offsets." icon={ShieldCheck} /><EvidenceList items={content.evidence} emptyLabel="No citations were included; review the handover before sharing." /></Card>
            <Card className="p-5"><SectionHeader title="Uncertainty and missing knowledge" icon={ShieldCheck} /><div className="grid gap-3 md:grid-cols-3"><div className="rounded-xl bg-violet-50 p-3 text-xs text-violet-800">{content.uncertainty?.excluded_by_status}</div><div className="rounded-xl bg-navy-50 p-3 text-xs text-navy-800">{content.uncertainty?.excluded_by_clearance}</div><div className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">Open questions: {content.uncertainty?.unresolved_questions?.join(', ') || 'none'}</div></div><p className="mt-3 text-xs text-slate-500">{content.metadata?.score_note}</p></Card>
          </div>}
        </div>
      </div>
      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Review and correct handover" wide><div className="space-y-4"><p className="text-sm text-slate-600">Edit the generated report before approval. A permission guard rejects any content above the recipient's clearance.</p><div><label className="label">Title</label><input className="input" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} /></div><div><label className="label">Report content (JSON)</label><textarea className="input min-h-[280px] font-mono !text-xs" value={editJson} onChange={(e) => setEditJson(e.target.value)} /></div><div><label className="label">Correction note</label><input className="input" value={editNote} onChange={(e) => setEditNote(e.target.value)} placeholder="What did the reviewer change?" /></div><div className="flex justify-end gap-2"><button className="btn-ghost" onClick={() => setEditOpen(false)}>Cancel</button><button className="btn-primary" disabled={busy === 'edit'} onClick={saveEdit}>Save correction</button></div></div></Modal>
    </div>
  );
}

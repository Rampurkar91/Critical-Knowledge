import { useState } from 'react';
import { LockKeyhole, UsersRound, ShieldCheck } from 'lucide-react';
import { api, projectPath } from '../lib/api';
import { useApiData } from '../lib/useApi';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { useToast } from '../context/ToastContext';
import { Badge, Card, EmptyState, ErrorPanel, Loading, SectionHeader, SensitivityPill } from '../components/ui';

const LEVELS = ['public', 'internal', 'confidential', 'restricted'];

export default function AccessManagement() {
  const { projectId, isManager } = useProject();
  const { meta } = useAuth();
  const { notify } = useToast();
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'incoming_engineer', max_clearance: 1 });
  const [busy, setBusy] = useState(false);
  const query = useApiData(() => api.get(projectPath(projectId, '/members')), [projectId], { enabled: Boolean(projectId && isManager) });
  const add = async (event) => { event.preventDefault(); setBusy(true); try { await api.post(projectPath(projectId, '/members'), { email: form.email, full_name: form.full_name || undefined, password: form.password || undefined, role: form.role, max_clearance: Number(form.max_clearance) }); notify('Project member added.', 'success'); setForm({ ...form, email: '', full_name: '', password: '' }); query.refresh(); } catch (e) { notify(e.message, 'error'); } finally { setBusy(false); } };
  const update = async (member, patch) => { try { await api.patch(`/api/members/${member.id}`, patch); notify(`${member.email} access updated.`, 'success'); query.refresh(); } catch (e) { notify(e.message, 'error'); } };
  if (!projectId) return <EmptyState title="No project selected" description="Select a project to manage access." />;
  if (!isManager) return <EmptyState icon={LockKeyhole} title="Manager access required" description="Only project managers can view or change access permissions." />;
  if (query.loading && !query.data) return <Loading />;
  if (query.error) return <ErrorPanel error={query.error} onRetry={query.refresh} />;
  const roles = Object.entries(meta?.roles || {});
  return (
    <div className="space-y-6 fade-in">
      <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">Role-based access control</p><h2 className="mt-1 text-2xl font-extrabold tracking-tight text-navy-950">Access and permission management</h2><p className="muted mt-1">Membership, role actions, claim-type allowlists and classification clearance are enforced before retrieval.</p></div>
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <Card className="overflow-hidden"><SectionHeader title={`Project members (${query.data?.length || 0})`} subtitle="Changes are written to the append-only audit trail." icon={UsersRound} /><div className="overflow-x-auto"><table className="w-full min-w-[940px] border-collapse"><thead><tr className="table-head"><th className="px-4 py-3">Member</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Clearance</th><th className="px-4 py-3">Claim types</th><th className="px-4 py-3">Policy</th></tr></thead><tbody>{(query.data || []).map((member) => <tr key={member.id}><td className="table-cell"><p className="font-semibold text-navy-900">{member.full_name}</p><p className="text-[11px] text-slate-500">{member.email}</p></td><td className="table-cell"><select className="input !w-auto !py-1.5 text-xs" value={member.role} onChange={(e) => update(member, { role: e.target.value })}>{roles.map(([key, policy]) => <option key={key} value={key}>{policy.label}</option>)}</select></td><td className="table-cell"><div className="flex items-center gap-2"><SensitivityPill label={member.clearance_label} level={member.clearance} /><select className="input !w-20 !py-1 text-xs" value={member.clearance} onChange={(e) => update(member, { max_clearance: Number(e.target.value) })}>{LEVELS.map((label, index) => <option key={label} value={index}>{index}</option>)}</select></div></td><td className="table-cell text-xs">{member.allowed_claim_types?.includes('*') ? 'All authorised types' : member.allowed_claim_types?.join(', ')}</td><td className="table-cell text-xs text-slate-500">{member.policy.description}</td></tr>)}</tbody></table></div></Card>
        <div className="space-y-5"><Card className="p-5"><SectionHeader title="Add member" subtitle="Existing users can be added by email." icon={UsersRound} /><form onSubmit={add} className="space-y-3"><div><label className="label">Email</label><input className="input !py-2" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></div><div><label className="label">Full name (new users)</label><input className="input !py-2" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div><div><label className="label">Password (new users only)</label><input className="input !py-2" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Leave blank for an existing user" /></div><div className="grid grid-cols-2 gap-3"><div><label className="label">Role</label><select className="input !py-2" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{roles.map(([key, policy]) => <option key={key} value={key}>{policy.label}</option>)}</select></div><div><label className="label">Clearance</label><select className="input !py-2" value={form.max_clearance} onChange={(e) => setForm({ ...form, max_clearance: Number(e.target.value) })}>{LEVELS.map((label, index) => <option key={label} value={index}>{index} · {label}</option>)}</select></div></div><button className="btn-primary w-full" disabled={busy}>{busy ? 'Adding…' : 'Add project member'}</button><p className="text-[11px] text-slate-500">Passwords are PBKDF2-hashed and never returned or logged.</p></form></Card><Card className="p-5"><SectionHeader title="Security boundary" icon={ShieldCheck} /><ul className="space-y-2 text-xs text-slate-600"><li>• Project membership is required for every project endpoint.</li><li>• Actions are checked against the project role policy.</li><li>• Classification is checked on sources, claims, graph nodes, edges, handovers and exports.</li><li>• Handovers are additionally scoped to the recipient.</li><li>• Generated text passes a restricted-phrase guard.</li></ul><div className="mt-3 flex flex-wrap gap-2">{LEVELS.map((label, index) => <SensitivityPill key={label} label={label} level={index} />)}</div></Card></div>
      </div>
    </div>
  );
}

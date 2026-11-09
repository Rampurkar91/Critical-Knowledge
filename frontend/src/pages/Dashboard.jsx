import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import {
  Activity, AlertTriangle, ArrowRight, CheckCircle2, Database, FileText,
  GitCompareArrows, Layers3, ShieldCheck, TriangleAlert,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { api, projectPath } from '../lib/api';
import { useApiData } from '../lib/useApi';
import { useProject } from '../context/ProjectContext';
import {
  Badge, Card, DemoBanner, EmptyState, ErrorPanel, Loading, SectionHeader,
  StatCard, StatusPill, formatDate, truncate,
} from '../components/ui';

const STATUS_COLORS = { Verified: '#10b981', 'Needs Review': '#f59e0b', Conflicting: '#ef4444', Unsupported: '#8b5cf6', Outdated: '#94a3b8' };

export default function Dashboard() {
  const { projectId, currentProject } = useProject();
  const query = useApiData(() => api.get(projectPath(projectId, '/dashboard')), [projectId], { enabled: Boolean(projectId) });
  if (!projectId) return <EmptyState title="No project selected" description="Create or select a project to view its continuity dashboard." />;
  if (query.loading && !query.data) return <Loading />;
  if (query.error) return <ErrorPanel error={query.error} onRetry={query.refresh} />;
  const data = query.data;
  const statusData = Object.entries(data.verification_status_counts || {}).map(([name, value]) => ({ name, value }));
  const taskData = Object.entries(data.task_status_counts || {}).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-6 fade-in">
      {data.demo_notice && <DemoBanner />}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">{currentProject?.key} · {data.project.clearance} clearance</p><h2 className="mt-1 text-2xl font-extrabold tracking-tight text-navy-950">{data.project.name}</h2><p className="muted mt-1 max-w-2xl">{data.project.description}</p></div>
        <div className="flex gap-2"><Link to="/graph" className="btn-outline"><Layers3 className="h-4 w-4" /> Explore graph</Link><Link to="/handover" className="btn-primary"><FileText className="h-4 w-4" /> Handovers</Link></div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard icon={Database} label="Authorised sources" value={data.stats.sources} hint="documents, exports and GitHub activity" />
        <StatCard icon={Layers3} label="Visible claims" value={data.stats.claims} hint="filtered by role and clearance" tone="navy" />
        <StatCard icon={CheckCircle2} label="Verified" value={data.verification_status_counts.Verified || 0} hint="approved with evidence" tone="teal" />
        <StatCard icon={GitCompareArrows} label="Open conflicts" value={data.open_conflicts} hint="require manager resolution" tone="rose" />
        <StatCard icon={Activity} label="Avg. heuristic score" value={data.average_reliability_score} hint="not a calibrated probability" tone="violet" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="p-5">
          <SectionHeader title="Verification status" subtitle="Claim-level reliability across authorised knowledge." icon={ShieldCheck} />
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="h-56"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={statusData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={78} paddingAngle={3}>{statusData.map((entry) => <Cell key={entry.name} fill={STATUS_COLORS[entry.name] || '#cbd5e1'} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div>
            <div className="flex flex-col justify-center gap-2">{statusData.map((entry) => <div key={entry.name} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"><span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLORS[entry.name] }} />{entry.name}</span><strong>{entry.value}</strong></div>)}</div>
          </div>
          <div className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-500">{data.score_disclaimer}</div>
        </Card>
        <Card className="p-5">
          <SectionHeader title="Task status" subtitle="Outstanding work visible to this role." icon={Activity} />
          <div className="h-56"><ResponsiveContainer width="100%" height="100%"><BarChart data={taskData}><XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="value" fill="#20a89a" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <SectionHeader title="Recently reconstructed knowledge" subtitle="Every item links back to exact source evidence." icon={Layers3} action={<Link to="/verification" className="link text-sm">View all <ArrowRight className="inline h-3 w-3" /></Link>} />
          <div className="space-y-3">
            {data.recent_claims.map((claim) => (
              <div key={claim.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2"><div className="flex items-center gap-2"><Badge tone="navy">{claim.claim_type.replace(/_/g, ' ')}</Badge><StatusPill status={claim.verification_status} /></div><span className="text-[11px] text-slate-400">{formatDate(claim.source_timestamp)}</span></div>
                <p className="mt-2 text-sm font-medium text-navy-900">{truncate(claim.statement, 180)}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500"><span>{claim.external_ref}</span><span>·</span><span>{claim.evidence?.length || 0} evidence span(s)</span><span>·</span><span>heuristic score {claim.reliability_score}</span></div>
              </div>
            ))}
            {!data.recent_claims.length && <p className="muted">No claims are visible yet. Ingest sources and run extraction.</p>}
          </div>
        </Card>
        <div className="space-y-5">
          <Card className="p-5"><SectionHeader title="High-priority tasks" icon={TriangleAlert} /><div className="space-y-2">{data.high_priority_tasks.map((task) => <div key={task.id} className="rounded-lg bg-slate-50 px-3 py-2"><p className="text-sm font-semibold text-navy-900">{task.external_ref} · {truncate(task.title, 70)}</p><p className="mt-1 text-[11px] text-slate-500">{task.owner || 'Unassigned'} · due {formatDate(task.due_date)} · {task.status}</p></div>)}{!data.high_priority_tasks.length && <p className="muted">No high-priority visible tasks.</p>}</div></Card>
          <Card className="p-5"><SectionHeader title="Open risks" icon={AlertTriangle} /><div className="space-y-2">{data.open_risks.map((risk) => <div key={risk.id} className="rounded-lg bg-rose-50/60 px-3 py-2"><p className="text-sm font-semibold text-rose-900">{truncate(risk.title, 82)}</p><p className="mt-1 text-[11px] text-rose-700">{risk.severity} severity · {risk.owner || 'Unassigned'}</p></div>)}{!data.open_risks.length && <p className="muted">No open visible risks.</p>}</div></Card>
        </div>
      </div>

      {data.handovers.length > 0 && (
        <Card className="p-5"><SectionHeader title="Handover pipeline" subtitle="Draft → approved → shared → acknowledged → completed." icon={FileText} action={<Link to="/handover" className="link text-sm">Open reports</Link>} /><div className="grid gap-3 md:grid-cols-3">{data.handovers.slice(0, 6).map((item) => <div key={item.id} className="rounded-xl border border-slate-200 p-3"><div className="flex items-center justify-between"><StatusPill status={item.status} /><Badge tone="slate">{item.clearance}</Badge></div><p className="mt-2 text-sm font-bold text-navy-900">{item.title}</p><p className="mt-1 text-[11px] text-slate-500">{item.recipient_role.replaceAll('_', ' ')} · {formatDate(item.generated_at, true)}</p></div>)}</div></Card>
      )}
    </div>
  );
}

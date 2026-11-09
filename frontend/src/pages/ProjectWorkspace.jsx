import { Sparkles, Workflow, ShieldCheck, FileCheck2, Share2, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api, projectPath } from '../lib/api';
import { useApiData } from '../lib/useApi';
import { useProject } from '../context/ProjectContext';
import { useToast } from '../context/ToastContext';
import {
  Badge, Card, DemoBanner, EmptyState, ErrorPanel, KeyValue, Loading,
  ProgressBar, SectionHeader, StatCard, StatusPill, formatDate,
} from '../components/ui';
import { useState } from 'react';

const safe = async (promise) => {
  try { return await promise; } catch { return null; }
};

export default function ProjectWorkspace() {
  const { projectId, can, isManager } = useProject();
  const { notify } = useToast();
  const [busy, setBusy] = useState('');
  const query = useApiData(async () => {
    const [project, sources, verification, graph, continuity, reviews, members] = await Promise.all([
      api.get(projectPath(projectId, '')),
      safe(api.get(projectPath(projectId, '/sources'))),
      safe(api.get(projectPath(projectId, '/verification/summary'))),
      safe(api.get(projectPath(projectId, '/graph'))),
      safe(api.get(projectPath(projectId, '/continuity'))),
      safe(api.get(projectPath(projectId, '/reviews'))),
      safe(api.get(projectPath(projectId, '/members'))),
    ]);
    return { project, sources, verification, graph, continuity, reviews, members };
  }, [projectId], { enabled: Boolean(projectId) });

  const runAction = async (name, path, body) => {
    setBusy(name);
    try {
      await api.post(path, body);
      notify(`${name} completed.`, 'success');
      query.refresh();
    } catch (error) {
      notify(error.message, 'error');
    } finally {
      setBusy('');
    }
  };

  if (!projectId) return <EmptyState title="No project selected" description="Create or select a project first." />;
  if (query.loading && !query.data) return <Loading />;
  if (query.error) return <ErrorPanel error={query.error} onRetry={query.refresh} />;
  const { project, sources, verification, graph, continuity, reviews, members } = query.data;
  const sourceCount = sources?.total || 0;
  const claimCount = verification?.claims_evaluated || 0;
  const verified = verification?.status_counts?.Verified || 0;
  const handovers = continuity?.handovers || [];
  const shared = handovers.filter((h) => ['shared', 'acknowledged', 'in_progress', 'completed'].includes(h.status)).length;
  const acknowledged = continuity?.items_acknowledged || 0;
  const completionRate = Math.round((continuity?.completion_rate || 0) * 100);

  const stages = [
    { title: 'Create project', detail: `${project.key} · ${project.status}`, done: true, link: '/access' },
    { title: 'Integrate sources', detail: `${sourceCount} authorised sources`, done: sourceCount > 0, link: '/sources' },
    { title: 'Extract knowledge', detail: `${claimCount} visible claims`, done: claimCount > 0, link: '/sources' },
    { title: 'Reconstruct graph', detail: `${graph?.nodes?.length || 0} nodes · ${graph?.edges?.length || 0} edges`, done: (graph?.nodes?.length || 0) > 0, link: '/graph' },
    { title: 'Verify evidence', detail: `${verification?.status_counts?.Conflicting || 0} conflicts · ${verification?.status_counts?.Unsupported || 0} unsupported`, done: claimCount > 0, link: '/verification' },
    { title: 'Human review', detail: `${reviews?.total || 0} review events · ${verified} verified`, done: verified > 0, link: '/review' },
    { title: 'Generate handover', detail: `${handovers.length} handover(s)`, done: handovers.length > 0, link: '/handover' },
    { title: 'Controlled sharing', detail: `${shared} shared or later`, done: shared > 0, link: '/handover' },
    { title: 'Continuation', detail: `${acknowledged} items acknowledged`, done: acknowledged > 0, link: '/incoming' },
    { title: 'Project continuity', detail: `${completionRate}% item completion`, done: completionRate > 0, link: '/continuity' },
  ];
  const completedStages = stages.filter((s) => s.done).length;

  return (
    <div className="space-y-6 fade-in">
      {project.is_demo && <DemoBanner />}
      <Card className="overflow-hidden">
        <div className="bg-navy-950 px-6 py-7 text-white">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div><p className="text-[10px] font-bold uppercase tracking-[0.2em] text-teal-300">{project.key} · {project.role?.replaceAll('_', ' ')}</p><h2 className="mt-2 text-3xl font-extrabold tracking-tight">{project.name}</h2><p className="mt-2 max-w-3xl text-sm leading-relaxed text-white/65">{project.description}</p></div>
            <div className="flex flex-wrap gap-2"><Badge tone="teal" className="!bg-teal-400/15 !text-teal-200">{project.clearance} clearance</Badge><StatusPill status={project.status} /></div>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-4">{project.stats && Object.entries(project.stats).map(([key, value]) => <div key={key} className="rounded-xl bg-white/5 px-4 py-3"><p className="text-[10px] uppercase tracking-wider text-white/45">{key}</p><p className="mt-1 text-xl font-bold">{value}</p></div>)}</div>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]">
        <Card className="p-5">
          <SectionHeader title="Ten-stage handover workflow" subtitle="Live status derived from authorised project data." icon={Workflow} action={<Badge tone="teal">{completedStages}/10 complete</Badge>} />
          <div className="mb-5"><ProgressBar value={(completedStages / 10) * 100} /><p className="mt-1.5 text-xs text-slate-500">Workflow progress is a completion indicator, not a probability.</p></div>
          <div className="grid gap-3 sm:grid-cols-2">
            {stages.map((stage, index) => (
              <Link key={stage.title} to={stage.link} className="rounded-xl border border-slate-200 p-3 transition hover:border-teal-300 hover:bg-teal-50/40">
                <div className="flex items-start gap-3"><span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold ${stage.done ? 'bg-teal-100 text-teal-700' : 'bg-slate-100 text-slate-500'}`}>{stage.done ? <CheckCircle2 className="h-4 w-4" /> : index + 1}</span><div><p className="text-sm font-bold text-navy-900">{stage.title}</p><p className="mt-0.5 text-xs text-slate-500">{stage.detail}</p></div></div>
              </Link>
            ))}
          </div>
        </Card>
        <div className="space-y-5">
          <Card className="p-5">
            <SectionHeader title="Manager actions" subtitle="Human-controlled reconstruction and approval." icon={Sparkles} />
            <div className="space-y-2">
              <button className="btn-primary w-full justify-start" disabled={!can('knowledge.extract') || Boolean(busy)} onClick={() => runAction('Knowledge reconstruction', projectPath(projectId, '/extract'), { reprocess: true })}>{busy === 'Knowledge reconstruction' ? 'Reconstructing…' : 'Re-run extraction & verification'}</button>
              <button className="btn-outline w-full justify-start" disabled={!can('review.approve') || Boolean(busy)} onClick={() => runAction('Eligible claim approval', projectPath(projectId, '/review/approve-eligible'), {})}>{busy === 'Eligible claim approval' ? 'Approving…' : 'Approve eligible claims'}</button>
              <Link to="/conflicts" className="btn-outline w-full justify-start"><ShieldCheck className="h-4 w-4" /> Resolve conflicts</Link>
              <Link to="/handover" className="btn-navy w-full justify-start"><Share2 className="h-4 w-4" /> Generate & share handover</Link>
            </div>
            {!isManager && <p className="mt-3 text-xs text-slate-500">Some actions require the project manager role.</p>}
          </Card>
          <Card className="p-5"><SectionHeader title="Project facts" icon={FileCheck2} /><KeyValue items={[{ label: 'Created', value: formatDate(project.created_at, true) }, { label: 'Organisation', value: project.organization_id?.slice(0, 12) }, { label: 'Data type', value: project.is_demo ? 'Synthetic demo' : 'User project' }, { label: 'Visible team', value: members?.length ? `${members.length} members` : 'Restricted to managers' }, { label: 'Review events', value: reviews?.total || 0 }, { label: 'Handover items', value: continuity?.items_total || 0 }]} /></Card>
        </div>
      </div>
    </div>
  );
}

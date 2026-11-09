import { Network, ShieldCheck, GitBranch, Clock3 } from 'lucide-react';
import GraphExplorer from '../components/GraphExplorer';
import { useProject } from '../context/ProjectContext';
import { Card, EmptyState, SectionHeader } from '../components/ui';

export default function KnowledgeGraph() {
  const { projectId, currentProject } = useProject();
  if (!projectId) return <EmptyState title="No project selected" description="Select a project to reconstruct its history." />;
  return (
    <div className="space-y-6 fade-in">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">Innovation 1 · Temporal knowledge graph</p><h2 className="mt-1 text-2xl font-extrabold tracking-tight text-navy-950">What happened, why, who, and what depends on it</h2><p className="muted mt-1">Move through project time, click a node and inspect the exact evidence that supports it.</p></div>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-4"><div className="flex gap-3"><span className="rounded-xl bg-teal-50 p-2 text-teal-700"><Network className="h-5 w-5" /></span><div><p className="font-bold text-navy-900">Relationships are temporal</p><p className="mt-1 text-xs leading-relaxed text-slate-500">Nodes and edges carry valid-from and valid-to dates. Superseded facts remain visible in historical views.</p></div></div></Card>
        <Card className="p-4"><div className="flex gap-3"><span className="rounded-xl bg-navy-50 p-2 text-navy-700"><GitBranch className="h-5 w-5" /></span><div><p className="font-bold text-navy-900">Decisions include reasons</p><p className="mt-1 text-xs leading-relaxed text-slate-500">Every decision node connects to an owner, supporting evidence and a separate “why” node.</p></div></div></Card>
        <Card className="p-4"><div className="flex gap-3"><span className="rounded-xl bg-violet-50 p-2 text-violet-700"><ShieldCheck className="h-5 w-5" /></span><div><p className="font-bold text-navy-900">Clearance propagates</p><p className="mt-1 text-xs leading-relaxed text-slate-500">An internal task pointing to a restricted decision produces a restricted edge; no hidden relationship leaks.</p></div></div></Card>
      </div>
      <GraphExplorer projectId={projectId} />
      <Card className="p-4 text-xs text-slate-500"><Clock3 className="mr-1 inline h-3.5 w-3.5" /> Graph data for {currentProject?.name || 'this project'} is filtered by project membership, classification clearance and claim-type allowlist before serialisation.</Card>
    </div>
  );
}

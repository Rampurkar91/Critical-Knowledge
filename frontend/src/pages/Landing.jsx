import { Link } from 'react-router-dom';
import {
  ArrowRight, CheckCircle2, GitBranch, LockKeyhole, Network, Quote,
  ShieldCheck, Sparkles, UserCheck, Workflow,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Badge } from '../components/ui';

const INNOVATIONS = [
  { icon: Network, title: 'Reconstruct', color: 'from-teal-500 to-teal-700', text: 'A temporal knowledge graph connects decisions, reasons, owners, dependencies and unfinished work — with clickable evidence.', points: ['Decision reconstruction', 'Task dependencies', 'State changes over time'] },
  { icon: ShieldCheck, title: 'Verify', color: 'from-navy-500 to-navy-800', text: 'Claim-level citations, conflict detection, outdated records and explainable heuristic reliability scores make uncertainty visible.', points: ['Exact source offsets', 'Five verification states', 'Human correction history'] },
  { icon: UserCheck, title: 'Continue', color: 'from-cyan-500 to-teal-700', text: 'Role-aware handovers apply clearance before retrieval, then deliver a personalised continuation checklist and acknowledgement trail.', points: ['Permission-aware RAG', 'Next five actions', 'Continuation tracking'] },
];

export default function Landing() {
  const { isAuthenticated } = useAuth();
  return (
    <div className="min-h-screen bg-navy-950 text-white">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5">
        <div className="flex items-center gap-3"><img src="/knowledgebridge-mark.svg" alt="" className="h-10 w-10" /><div><p className="font-extrabold tracking-tight">KnowledgeBridge</p><p className="text-[10px] uppercase tracking-[0.2em] text-teal-300">Preserve Knowledge. Empower Continuity.</p></div></div>
        <nav className="hidden items-center gap-7 text-sm text-white/70 md:flex"><a href="#innovations" className="hover:text-white">Innovations</a><a href="#workflow" className="hover:text-white">Workflow</a><a href="#trust" className="hover:text-white">Trust</a></nav>
        <Link to={isAuthenticated ? '/dashboard' : '/login'} className="btn bg-white/10 text-white ring-1 ring-white/20 hover:bg-white/20">{isAuthenticated ? 'Open workspace' : 'Sign in'} <ArrowRight className="h-4 w-4" /></Link>
      </header>

      <section className="hero-network grid-pattern relative overflow-hidden border-y border-white/10">
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 py-20 lg:grid-cols-[1.05fr_0.95fr] lg:py-28">
          <div className="fade-in">
            <Badge tone="teal" className="!bg-teal-400/15 !text-teal-200 !ring-teal-300/30"><Sparkles className="h-3 w-3" /> National Hackathon · Round 3</Badge>
            <h1 className="mt-6 max-w-3xl text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">Critical knowledge should never <span className="bg-gradient-to-r from-teal-300 to-cyan-300 bg-clip-text text-transparent">leave with people.</span></h1>
            <p className="mt-6 max-w-2xl text-base leading-relaxed text-white/70 sm:text-lg">KnowledgeBridge transforms scattered project activity into trusted, actionable and permission-aware knowledge — reconstructing decisions, verifying every important claim and delivering secure, role-specific handovers.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={isAuthenticated ? '/dashboard' : '/login'} className="btn bg-teal-500 px-5 py-3 text-white hover:bg-teal-400">Launch demonstration <ArrowRight className="h-4 w-4" /></Link>
              <a href="#innovations" className="btn border border-white/20 bg-white/5 px-5 py-3 text-white hover:bg-white/10">Explore innovations</a>
            </div>
            <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-sm text-white/60">
              <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-teal-300" /> Evidence-linked claims</span>
              <span className="flex items-center gap-2"><LockKeyhole className="h-4 w-4 text-teal-300" /> Clearance before retrieval</span>
              <span className="flex items-center gap-2"><Workflow className="h-4 w-4 text-teal-300" /> End-to-end demo workflow</span>
            </div>
          </div>
          <div className="relative hidden lg:block">
            <div className="absolute -inset-8 rounded-full bg-teal-500/10 blur-3xl" />
            <div className="relative rounded-3xl border border-white/15 bg-navy-900/70 p-6 shadow-2xl backdrop-blur-xl">
              <div className="flex items-center justify-between"><p className="text-xs font-bold uppercase tracking-widest text-teal-300">Project intelligence</p><Badge tone="teal" className="!bg-teal-400/10 !text-teal-200">Live demo</Badge></div>
              <div className="mt-6 grid grid-cols-3 gap-3 text-center">
                {[['94', 'claims'], ['210', 'graph edges'], ['10', 'sources']].map(([value, label]) => <div key={label} className="rounded-2xl bg-white/5 p-4"><p className="text-2xl font-bold text-white">{value}</p><p className="text-[11px] uppercase tracking-wider text-white/45">{label}</p></div>)}
              </div>
              <div className="mt-6 space-y-3">
                {[['Reconstruct', 'Decision → reason → dependency', '82%'], ['Verify', '2 conflicts · 2 outdated · 1 unsupported', '64%'], ['Continue', '5 role-specific next actions', '91%']].map(([label, detail, pct]) => (
                  <div key={label} className="rounded-xl border border-white/10 bg-white/5 p-3"><div className="flex justify-between text-xs"><span className="font-semibold text-white">{label}</span><span className="text-teal-300">{pct}</span></div><p className="mt-1 text-[11px] text-white/50">{detail}</p><div className="mt-2 h-1.5 rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-teal-400 to-cyan-300" style={{ width: pct }} /></div></div>
                ))}
              </div>
              <p className="mt-5 text-[10px] leading-relaxed text-white/40">Illustrative counts from the synthetic demonstration dataset; percentages are visual placeholders, not measured probabilities.</p>
            </div>
          </div>
        </div>
      </section>

      <section id="innovations" className="mx-auto max-w-7xl px-5 py-20">
        <div className="max-w-2xl"><p className="text-xs font-bold uppercase tracking-[0.2em] text-teal-300">Three functional differentiators</p><h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">Reconstruct. Verify. Continue.</h2><p className="mt-4 text-white/60">Three implemented modules work together to solve knowledge loss as an evidence, security and continuity problem — not just a document-summarisation problem.</p></div>
        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {INNOVATIONS.map((item, index) => (
            <div key={item.title} className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 transition hover:border-teal-400/30 hover:bg-white/[0.07]">
              <div className={`grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br ${item.color}`}><item.icon className="h-5 w-5" /></div>
              <p className="mt-5 text-[11px] font-bold uppercase tracking-[0.18em] text-teal-300">0{index + 1}</p>
              <h3 className="mt-1 text-xl font-bold">{item.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-white/60">{item.text}</p>
              <ul className="mt-5 space-y-2 text-sm text-white/75">{item.points.map((point) => <li key={point} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-400" />{point}</li>)}</ul>
            </div>
          ))}
        </div>
      </section>

      <section id="workflow" className="border-y border-white/10 bg-white/[0.03]">
        <div className="mx-auto max-w-7xl px-5 py-16">
          <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-teal-300">Complete workflow</p><h2 className="mt-3 text-3xl font-extrabold">Ten stages, one auditable trail.</h2></div><Link to="/login" className="btn bg-teal-500 text-white hover:bg-teal-400">Start the walkthrough <ArrowRight className="h-4 w-4" /></Link></div>
          <div className="mt-9 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {['Create project', 'Integrate sources', 'Extract knowledge', 'Reconstruct graph', 'Verify evidence', 'Human review', 'Generate handover', 'Controlled sharing', 'Continuation', 'Project continuity'].map((stage, index) => (
              <div key={stage} className="rounded-xl border border-white/10 bg-navy-900/60 p-4"><p className="text-xs font-bold text-teal-300">Stage {index + 1}</p><p className="mt-2 text-sm font-semibold text-white">{stage}</p></div>
            ))}
          </div>
        </div>
      </section>

      <section id="trust" className="mx-auto grid max-w-7xl gap-10 px-5 py-20 lg:grid-cols-2">
        <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-teal-300">Built for trustworthy handovers</p><h2 className="mt-3 text-3xl font-extrabold">Every statement points back to evidence.</h2><p className="mt-4 leading-relaxed text-white/60">KnowledgeBridge never fabricates citations. Unsupported claims are labelled, conflicts remain visible until resolved, and reliability scores are explained as heuristics — not statistical probabilities. Restricted information is filtered before retrieval, not removed only at display time.</p></div>
        <div className="rounded-2xl border border-white/10 bg-navy-900/70 p-7"><Quote className="h-7 w-7 text-teal-400" /><p className="mt-4 text-xl font-semibold leading-relaxed text-white">“KnowledgeBridge transforms scattered project activity into trusted, actionable and permission-aware knowledge, ensuring that critical knowledge never leaves with people.”</p><div className="mt-6 flex items-center gap-3 text-sm text-white/50"><GitBranch className="h-4 w-4" /><span>Research-grounded · evidence-first · role-aware</span></div></div>
      </section>

      <footer className="border-t border-white/10 px-5 py-8 text-center text-xs text-white/40">© 2026 KnowledgeBridge · Synthetic demonstration data · Hackathon Round 3</footer>
    </div>
  );
}

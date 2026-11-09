import { useMemo, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity, Bot, ChevronDown, Database, FileCheck2, FileText, FolderKanban,
  GitBranch, GitCompareArrows, LayoutDashboard, LogOut, Menu, Network,
  ScrollText, ShieldCheck, Sparkles, TriangleAlert, UserCheck, UsersRound, X,
} from 'lucide-react';
import { api, projectPath } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { useToast } from '../context/ToastContext';
import { Badge, Drawer, EvidenceList, Modal, SensitivityPill } from './ui';

const NAV_GROUPS = [
  {
    label: 'Workspace',
    items: [
      { to: '/dashboard', label: 'Main Dashboard', icon: LayoutDashboard },
      { to: '/workspace', label: 'Project Workspace', icon: FolderKanban },
      { to: '/sources', label: 'Source Integration', icon: Database },
    ],
  },
  {
    label: 'Reconstruct & Verify',
    items: [
      { to: '/graph', label: 'Knowledge Graph', icon: Network },
      { to: '/decisions', label: 'Decision History', icon: GitBranch },
      { to: '/verification', label: 'Evidence Verification', icon: ShieldCheck },
      { to: '/conflicts', label: 'Conflict Detection', icon: GitCompareArrows },
      { to: '/risks', label: 'Risks & Dependencies', icon: TriangleAlert },
    ],
  },
  {
    label: 'Continue',
    items: [
      { to: '/review', label: 'Review & Approval', icon: FileCheck2 },
      { to: '/handover', label: 'Handover Report', icon: FileText },
      { to: '/incoming', label: 'Incoming Dashboard', icon: UserCheck },
      { to: '/continuity', label: 'Project Continuity', icon: Activity },
    ],
  },
  {
    label: 'Governance',
    items: [
      { to: '/access', label: 'Access & Permissions', icon: UsersRound },
      { to: '/audit', label: 'Audit History', icon: ScrollText },
    ],
  },
];

const TITLES = NAV_GROUPS.flatMap((group) => group.items).reduce((acc, item) => ({ ...acc, [item.to]: item.label }), {});

function SidebarContent({ onNavigate }) {
  const { role, policy, isManager } = useProject();
  return (
    <div className="flex h-full flex-col bg-navy-950 text-white">
      <Link to="/dashboard" onClick={onNavigate} className="flex items-center gap-3 border-b border-white/10 px-5 py-5">
        <img src="/knowledgebridge-mark.svg" alt="" className="h-9 w-9 rounded-xl" />
        <div>
          <p className="text-sm font-extrabold tracking-tight">KnowledgeBridge</p>
          <p className="text-[10px] uppercase tracking-[0.18em] text-teal-300">Preserve · Verify · Continue</p>
        </div>
      </Link>
      <nav className="sidebar-scroll flex-1 overflow-y-auto px-3 py-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="mb-5">
            <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-white/35">{group.label}</p>
            <div className="space-y-1">
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onNavigate}
                  className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all ${
                    isActive ? 'bg-teal-500/15 text-teal-200 ring-1 ring-teal-400/20' : 'text-white/65 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  <item.icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-white/10 px-4 py-4">
        <div className="rounded-xl bg-white/5 p-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-white/45">Project role</span>
            {isManager && <Sparkles className="h-3.5 w-3.5 text-teal-300" />}
          </div>
          <p className="mt-1 text-sm font-semibold text-white">{policy?.label || role || 'No role'}</p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-white/45">Permission-aware retrieval is active on every view.</p>
        </div>
      </div>
    </div>
  );
}

function AskDialog({ open, onClose }) {
  const { projectId } = useProject();
  const [question, setQuestion] = useState('What should the incoming engineer do first?');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const { notify } = useToast();
  const submit = async (event) => {
    event.preventDefault();
    if (!projectId) return;
    setLoading(true);
    try {
      const result = await api.post(projectPath(projectId, '/ask'), { question, top_k: 5 });
      setAnswer(result);
    } catch (error) {
      notify(error.message, 'error');
    } finally {
      setLoading(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="Ask KnowledgeBridge" wide>
      <form onSubmit={submit} className="space-y-3">
        <label className="label">Question</label>
        <div className="flex gap-2">
          <input className="input" value={question} onChange={(e) => setQuestion(e.target.value)} minLength={3} required />
          <button className="btn-primary" disabled={loading}>{loading ? 'Searching…' : 'Ask'}</button>
        </div>
        <p className="text-xs text-slate-500">Only evidence authorised for your project role and clearance is retrieved.</p>
      </form>
      {answer && (
        <div className="mt-5 space-y-4">
          <div className="rounded-xl border border-teal-200 bg-teal-50/70 p-4">
            <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-teal-800">
              <Bot className="h-4 w-4" /> {answer.provider}
            </div>
            <p className="whitespace-pre-line text-sm leading-relaxed text-navy-900">{answer.answer}</p>
          </div>
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">Authorised citations</p>
            <EvidenceList items={answer.citations?.map((c) => ({ ...c, evidence_id: c.claim_id }))} emptyLabel="No authorised evidence was retrieved." />
          </div>
          <p className="text-xs text-slate-500">{answer.score_disclaimer}</p>
        </div>
      )}
    </Modal>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { projects, projectId, currentProject, role, policy, setSelectedProjectId } = useProject();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [askOpen, setAskOpen] = useState(false);
  const title = TITLES[location.pathname] || 'KnowledgeBridge';
  const initials = useMemo(() => (user?.full_name || user?.email || 'KB').split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase(), [user]);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen lg:flex">
      <aside className="hidden w-[264px] shrink-0 lg:block"><div className="fixed h-screen w-[264px]"><SidebarContent /></div></aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-navy-950/50" onClick={() => setMobileOpen(false)} />
          <div className="relative h-full w-[280px]"><SidebarContent onNavigate={() => setMobileOpen(false)} /><button className="absolute right-3 top-4 rounded-lg p-2 text-white/70 hover:bg-white/10" onClick={() => setMobileOpen(false)}><X className="h-5 w-5" /></button></div>
        </div>
      )}
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/85 backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
            <div className="flex items-center gap-3">
              <button className="btn-ghost !p-2 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu className="h-5 w-5" /></button>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-teal-700">KnowledgeBridge</p>
                <h1 className="text-lg font-bold tracking-tight text-navy-950">{title}</h1>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {projects.length > 0 && (
                <label className="relative">
                  <span className="sr-only">Select project</span>
                  <select className="input !w-auto !py-2 !pr-8 text-xs font-semibold" value={projectId || ''} onChange={(e) => setSelectedProjectId(e.target.value)}>
                    {projects.map((project) => <option key={project.id} value={project.id}>{project.key} · {project.name}</option>)}
                  </select>
                </label>
              )}
              {currentProject?.clearance && <SensitivityPill label={currentProject.clearance} level={currentProject.clearance_level} />}
              <button className="btn-outline !py-2" onClick={() => setAskOpen(true)}><Bot className="h-4 w-4" /> Ask KB</button>
              <div className="relative">
                <button className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-2 py-1.5 hover:bg-slate-50" onClick={() => setProfileOpen((value) => !value)}>
                  <span className="grid h-8 w-8 place-items-center rounded-lg bg-navy-900 text-xs font-bold text-white">{initials}</span>
                  <span className="hidden text-left sm:block"><span className="block text-xs font-bold text-navy-900">{user?.full_name}</span><span className="block text-[10px] text-slate-500">{policy?.label || role}</span></span>
                  <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                </button>
                {profileOpen && (
                  <div className="absolute right-0 top-full z-40 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-panel">
                    <p className="text-xs font-semibold text-navy-900">{user?.email}</p>
                    <p className="mt-1 text-xs text-slate-500">{currentProject?.is_demo ? 'Synthetic demonstration project' : 'Active project workspace'}</p>
                    <div className="mt-3 flex flex-wrap gap-2"><Badge tone="navy">{policy?.label || role}</Badge>{currentProject?.clearance && <SensitivityPill label={currentProject.clearance} level={currentProject.clearance_level} />}</div>
                    <button className="btn-ghost mt-3 w-full justify-start !px-2" onClick={handleLogout}><LogOut className="h-4 w-4" /> Sign out</button>
                  </div>
                )}
              </div>
            </div>
          </div>
          {currentProject?.is_demo && <div className="border-t border-teal-100 bg-teal-50/60 px-4 py-1.5 text-center text-[11px] font-medium text-teal-800 sm:px-6">Demonstration data · synthetic Atlas Migration records · no real secrets or documents</div>}
        </header>
        <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8"><Outlet /></main>
      </div>
      <AskDialog open={askOpen} onClose={() => setAskOpen(false)} />
    </div>
  );
}

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Eye, FlaskConical, LockKeyhole, ShieldCheck, UserPlus } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Badge } from '../components/ui';

export default function AuthPage({ mode = 'login' }) {
  const [activeMode, setActiveMode] = useState(mode);
  const [form, setForm] = useState({ email: 'manager@knowledgebridge.demo', password: '', full_name: '', organization_name: 'KnowledgeBridge Demo Org' });
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState('');
  const { login, register, demoLogin, meta } = useAuth();
  const { notify } = useToast();
  const navigate = useNavigate();

  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      if (activeMode === 'login') await login(form.email, form.password);
      else await register({
        email: form.email,
        password: form.password,
        full_name: form.full_name,
        organization_name: form.organization_name || undefined,
      });
      notify('Welcome to KnowledgeBridge.', 'success');
      navigate('/dashboard');
    } catch (error) {
      notify(error.message, 'error');
    } finally {
      setBusy(false);
    }
  };
  const enterDemo = async (email) => {
    setDemoBusy(email);
    try {
      await demoLogin(email);
      notify(`Signed in as ${email}`, 'success');
      navigate('/dashboard');
    } catch (error) {
      notify(error.message, 'error');
    } finally {
      setDemoBusy('');
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hero-network grid-pattern hidden flex-col justify-between p-10 text-white lg:flex">
        <Link to="/" className="flex items-center gap-3"><img src="/knowledgebridge-mark.svg" alt="" className="h-10 w-10" /><span className="font-extrabold">KnowledgeBridge</span></Link>
        <div className="max-w-lg">
          <Badge tone="teal" className="!bg-teal-400/15 !text-teal-200 !ring-teal-300/30"><FlaskConical className="h-3 w-3" /> Synthetic demonstration</Badge>
          <h2 className="mt-6 text-4xl font-extrabold leading-tight">Preserve knowledge.<br />Empower continuity.</h2>
          <p className="mt-5 text-white/65">Reconstruct project history, verify every important claim with evidence and share only what each incoming member is authorised to see.</p>
          <div className="mt-8 space-y-3 text-sm text-white/70">
            {['Temporal decision graph with source inspection', 'Conflict, outdated and unsupported claim detection', 'Role-aware handovers with acknowledgement tracking'].map((item) => <p key={item} className="flex gap-3"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-teal-300" />{item}</p>)}
          </div>
        </div>
        <p className="text-xs text-white/40">No real documents, API keys or confidential records are included.</p>
      </div>

      <div className="flex items-center justify-center bg-slate-50 px-5 py-10">
        <div className="w-full max-w-md">
          <Link to="/" className="mb-8 flex items-center gap-2 text-sm font-semibold text-navy-800 lg:hidden"><img src="/knowledgebridge-mark.svg" alt="" className="h-8 w-8" /> KnowledgeBridge</Link>
          <div className="card p-7 fade-in">
            <div className="mb-6 flex rounded-xl bg-slate-100 p-1">
              {['login', 'register'].map((item) => (
                <button key={item} className={`flex-1 rounded-lg px-3 py-2 text-sm font-bold capitalize transition ${activeMode === item ? 'bg-white text-navy-900 shadow-sm' : 'text-slate-500'}`} onClick={() => setActiveMode(item)}>{item === 'login' ? 'Sign in' : 'Create account'}</button>
              ))}
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-navy-950">{activeMode === 'login' ? 'Welcome back' : 'Create your workspace'}</h1>
            <p className="muted mt-1">{activeMode === 'login' ? 'Sign in to continue a project handover.' : 'Register an organisation and start a new project.'}</p>

            <form onSubmit={submit} className="mt-6 space-y-4">
              {activeMode === 'register' && <div><label className="label">Full name</label><input className="input" value={form.full_name} onChange={update('full_name')} required minLength={2} placeholder="Your name" /></div>}
              <div><label className="label">Email</label><input className="input" type="email" value={form.email} onChange={update('email')} required placeholder="you@organisation.com" /></div>
              <div><label className="label">Password</label><div className="relative"><input className="input !pr-10" type="password" value={form.password} onChange={update('password')} required minLength={8} placeholder="••••••••" /><LockKeyhole className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-slate-400" /></div><p className="mt-1 text-[11px] text-slate-500">For the seeded demo use the <code>DEMO_PASSWORD</code> value from <code>.env.example</code>.</p></div>
              {activeMode === 'register' && <div><label className="label">Organisation</label><input className="input" value={form.organization_name} onChange={update('organization_name')} placeholder="Organisation name" /></div>}
              <button className="btn-primary w-full" disabled={busy}>{busy ? 'Please wait…' : activeMode === 'login' ? 'Sign in' : 'Create account'} {activeMode === 'login' ? <ArrowRight className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}</button>
            </form>

            {meta?.demo_mode && (
              <div className="mt-7 border-t border-slate-200 pt-6">
                <div className="mb-3 flex items-center justify-between"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Development demo accounts</p><Badge tone="teal"><Eye className="h-3 w-3" /> one click</Badge></div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {(meta.demo_accounts || []).map((account) => (
                    <button key={account.email} className="btn-outline !justify-start !px-3 !py-2 text-left" disabled={Boolean(demoBusy)} onClick={() => enterDemo(account.email)}>
                      <span className="min-w-0"><span className="block truncate text-xs font-bold text-navy-900">{account.role.replaceAll('_', ' ')}</span><span className="block truncate text-[10px] font-normal text-slate-500">{account.email.split('@')[0]}</span></span>
                    </button>
                  ))}
                </div>
                <p className="mt-3 text-[11px] leading-relaxed text-slate-500">Passwordless demo login is enabled only in development. The ordinary login form still uses PBKDF2-hashed passwords and JWTs.</p>
              </div>
            )}
          </div>
          <p className="mt-5 text-center text-xs text-slate-500"><Link to="/" className="link">Back to landing page</Link> · Synthetic demonstration data</p>
        </div>
      </div>
    </div>
  );
}

import { useState } from 'react';
import {
  CloudUpload, Database, ExternalLink, FileText, Github, Link2,
  RefreshCw, ShieldCheck, UploadCloud,
} from 'lucide-react';
import { api, projectPath } from '../lib/api';
import { useApiData } from '../lib/useApi';
import { useProject } from '../context/ProjectContext';
import { useToast } from '../context/ToastContext';
import {
  Badge, Card, DemoBanner, Drawer, EmptyState, ErrorPanel, EvidenceList,
  Loading, SectionHeader, SensitivityPill, StatusPill, formatDate,
} from '../components/ui';

const SOURCE_TYPES = ['project_document', 'meeting_note', 'decision_log', 'task_export', 'chat_export', 'risk_register', 'handover_note', 'github_commit', 'github_issue'];

export default function SourceIntegration() {
  const { projectId, can } = useProject();
  const { notify } = useToast();
  const query = useApiData(() => api.get(projectPath(projectId, '/sources')), [projectId], { enabled: Boolean(projectId) });
  const [activeSource, setActiveSource] = useState(null);
  const [sourceDetail, setSourceDetail] = useState(null);
  const [busy, setBusy] = useState('');
  const [file, setFile] = useState(null);
  const [textForm, setTextForm] = useState({ title: '', content: '', source_type: 'meeting_note', author: '', sensitivity: 1, source_date: '' });
  const [githubForm, setGithubForm] = useState({ repository: '', branch: 'main', max_commits: 10, max_issues: 10, sensitivity: 1 });

  const refresh = () => query.refresh();
  const withBusy = async (name, fn, success) => {
    setBusy(name);
    try {
      const result = await fn();
      notify(success || `${name} completed.`, 'success');
      refresh();
      return result;
    } catch (error) {
      notify(error.message, 'error');
      return null;
    } finally {
      setBusy('');
    }
  };

  const upload = async (event) => {
    event.preventDefault();
    if (!file) return notify('Choose a file first.', 'warning');
    const form = new FormData();
    form.append('file', file);
    form.append('source_type', textForm.source_type);
    form.append('author', textForm.author);
    form.append('sensitivity', String(textForm.sensitivity));
    await withBusy('upload', () => api.upload(projectPath(projectId, '/sources/upload'), form), 'Authorised source uploaded. Run extraction to reconstruct knowledge.');
    setFile(null);
  };
  const paste = async (event) => {
    event.preventDefault();
    await withBusy('paste', () => api.post(projectPath(projectId, '/sources/text'), {
      title: textForm.title,
      content: textForm.content,
      source_type: textForm.source_type,
      author: textForm.author,
      sensitivity: Number(textForm.sensitivity),
      source_date: textForm.source_date || undefined,
    }), 'Text source ingested.');
    setTextForm((current) => ({ ...current, title: '', content: '' }));
  };
  const connectGithub = async (event) => {
    event.preventDefault();
    await withBusy('github', () => api.post(projectPath(projectId, '/sources/github/connect'), {
      ...githubForm,
      max_commits: Number(githubForm.max_commits),
      max_issues: Number(githubForm.max_issues),
      sensitivity: Number(githubForm.sensitivity),
    }), 'GitHub activity ingested from the read-only API.');
  };
  const extract = async () => withBusy('extract', () => api.post(projectPath(projectId, '/extract'), { reprocess: false }), 'New sources processed; graph and verification refreshed.');
  const openSource = async (source) => {
    setActiveSource(source);
    setSourceDetail(null);
    try {
      setSourceDetail(await api.get(`/api/sources/${source.id}/content`));
    } catch (error) {
      notify(error.message, 'error');
      setActiveSource(null);
    }
  };

  if (!projectId) return <EmptyState title="No project selected" description="Select a project to integrate authorised sources." />;
  if (query.loading && !query.data) return <Loading />;
  if (query.error) return <ErrorPanel error={query.error} onRetry={query.refresh} />;
  const sources = query.data.items || [];
  const canIngest = can('source.ingest');
  const canConnect = can('source.connect');

  return (
    <div className="space-y-6 fade-in">
      <DemoBanner compact />
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-2xl font-extrabold tracking-tight text-navy-950">Authorised source integration</h2><p className="muted mt-1">Upload documents, paste structured notes or connect a GitHub repository. Classification is checked before storage.</p></div><button className="btn-primary" disabled={!can('knowledge.extract') || Boolean(busy)} onClick={extract}><RefreshCw className="h-4 w-4" /> {busy === 'extract' ? 'Extracting…' : 'Run extraction & verification'}</button></div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-5">
          <SectionHeader title="Upload document" subtitle=".md, .txt, .csv, .json or text-based PDF" icon={UploadCloud} />
          <form onSubmit={upload} className="space-y-3">
            <div><label className="label">File</label><input className="input !py-2" type="file" accept=".md,.txt,.csv,.json,.log,.pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} disabled={!canIngest} /></div>
            <div><label className="label">Source type</label><select className="input !py-2" value={textForm.source_type} onChange={(e) => setTextForm({ ...textForm, source_type: e.target.value })}>{SOURCE_TYPES.map((type) => <option key={type}>{type}</option>)}</select></div>
            <div className="grid grid-cols-2 gap-3"><div><label className="label">Author</label><input className="input !py-2" value={textForm.author} onChange={(e) => setTextForm({ ...textForm, author: e.target.value })} placeholder="Optional" /></div><div><label className="label">Classification</label><select className="input !py-2" value={textForm.sensitivity} onChange={(e) => setTextForm({ ...textForm, sensitivity: Number(e.target.value) })}>{[0, 1, 2, 3].map((level) => <option key={level} value={level}>{['public', 'internal', 'confidential', 'restricted'][level]}</option>)}</select></div></div>
            <button className="btn-primary w-full" disabled={!canIngest || busy === 'upload'}><CloudUpload className="h-4 w-4" /> {busy === 'upload' ? 'Uploading…' : 'Upload authorised source'}</button>
            {!canIngest && <p className="text-xs text-slate-500">Your role cannot ingest sources.</p>}
          </form>
        </Card>

        <Card className="p-5">
          <SectionHeader title="Paste source text" subtitle="Structured @record lines produce exact evidence offsets." icon={FileText} />
          <form onSubmit={paste} className="space-y-3">
            <div><label className="label">Title</label><input className="input !py-2" value={textForm.title} onChange={(e) => setTextForm({ ...textForm, title: e.target.value })} required placeholder="Sprint review note" /></div>
            <div><label className="label">Content</label><textarea className="input min-h-[112px] font-mono !text-xs" value={textForm.content} onChange={(e) => setTextForm({ ...textForm, content: e.target.value })} required placeholder={'@decision id=DEC-NEW key="api.mode" value="Read only beta" rationale="..." owner="..." status=approved tags=api sensitivity=internal'} /></div>
            <div className="grid grid-cols-2 gap-3"><div><label className="label">Date</label><input className="input !py-2" type="date" value={textForm.source_date} onChange={(e) => setTextForm({ ...textForm, source_date: e.target.value })} /></div><div><label className="label">Classification</label><select className="input !py-2" value={textForm.sensitivity} onChange={(e) => setTextForm({ ...textForm, sensitivity: Number(e.target.value) })}>{[0, 1, 2, 3].map((level) => <option key={level} value={level}>{['public', 'internal', 'confidential', 'restricted'][level]}</option>)}</select></div></div>
            <button className="btn-outline w-full" disabled={!canIngest || busy === 'paste'}>Ingest text</button>
          </form>
        </Card>

        <Card className="p-5">
          <SectionHeader title="GitHub API" subtitle="Read-only commits and issues; no token is stored." icon={Github} />
          <form onSubmit={connectGithub} className="space-y-3">
            <div><label className="label">Repository</label><input className="input !py-2" value={githubForm.repository} onChange={(e) => setGithubForm({ ...githubForm, repository: e.target.value })} required placeholder="owner/repository or GitHub URL" /></div>
            <div className="grid grid-cols-2 gap-3"><div><label className="label">Branch</label><input className="input !py-2" value={githubForm.branch} onChange={(e) => setGithubForm({ ...githubForm, branch: e.target.value })} /></div><div><label className="label">Classification</label><select className="input !py-2" value={githubForm.sensitivity} onChange={(e) => setGithubForm({ ...githubForm, sensitivity: Number(e.target.value) })}>{[0, 1, 2, 3].map((level) => <option key={level} value={level}>{['public', 'internal', 'confidential', 'restricted'][level]}</option>)}</select></div></div>
            <div className="grid grid-cols-2 gap-3"><div><label className="label">Commits</label><input className="input !py-2" type="number" min="1" max="50" value={githubForm.max_commits} onChange={(e) => setGithubForm({ ...githubForm, max_commits: e.target.value })} /></div><div><label className="label">Issues</label><input className="input !py-2" type="number" min="0" max="50" value={githubForm.max_issues} onChange={(e) => setGithubForm({ ...githubForm, max_issues: e.target.value })} /></div></div>
            <button className="btn-navy w-full" disabled={!canConnect || busy === 'github'}><Link2 className="h-4 w-4" /> {busy === 'github' ? 'Connecting…' : 'Connect repository'}</button>
            <p className="text-[11px] leading-relaxed text-slate-500">Optional <code>GITHUB_TOKEN</code> is read from the server environment only. Live API failures are reported; they are never replaced with invented evidence.</p>
          </form>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <SectionHeader title={`Ingested sources (${sources.length})`} subtitle="Click a row to inspect exact evidence spans and original content." icon={Database} />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] border-collapse">
            <thead><tr className="table-head"><th className="px-4 py-3">Source</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Classification</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Reference</th></tr></thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.id} className="cursor-pointer hover:bg-teal-50/40" onClick={() => openSource(source)}>
                  <td className="table-cell"><p className="font-semibold text-navy-900">{source.title}</p><p className="mt-0.5 text-[11px] text-slate-500">{source.source_ref} · {source.author || 'unknown author'}</p></td>
                  <td className="table-cell"><Badge tone="navy">{source.source_type.replaceAll('_', ' ')}</Badge></td>
                  <td className="table-cell">{formatDate(source.source_timestamp)}</td>
                  <td className="table-cell"><SensitivityPill label={source.sensitivity} level={source.sensitivity_level} /></td>
                  <td className="table-cell"><StatusPill status={source.processed_at ? 'Verified' : 'pending'} label={source.processed_at ? 'processed' : 'pending'} /></td>
                  <td className="table-cell max-w-[220px] truncate text-xs"><span className="flex items-center gap-1 text-teal-700">{source.external_ref || 'local'} <ExternalLink className="h-3 w-3" /></span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!sources.length && <div className="p-6"><EmptyState title="No sources visible" description="Ingest an authorised source or sign in with a higher-clearance role." /></div>}
        </div>
      </Card>

      <Drawer open={Boolean(activeSource)} onClose={() => { setActiveSource(null); setSourceDetail(null); }} title={activeSource?.title || 'Source'} subtitle={activeSource ? `${activeSource.source_ref} · ${activeSource.sensitivity}` : ''} wide>
        {!sourceDetail && <Loading label="Loading authorised source content…" />}
        {sourceDetail && (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-2"><SensitivityPill label={sourceDetail.sensitivity} level={sourceDetail.sensitivity_level} /><Badge tone="navy">{sourceDetail.source_type}</Badge>{sourceDetail.is_demo && <Badge tone="teal">Synthetic demo</Badge>}{sourceDetail.redacted && <Badge tone="rose">Guard redacted content</Badge>}</div>
            <div><h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">Original content</h4><pre className="max-h-[320px] overflow-auto rounded-xl bg-navy-950 p-4 text-[11px] leading-relaxed text-teal-50">{sourceDetail.content}</pre></div>
            <div><h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">Evidence spans ({sourceDetail.evidence_spans?.length || 0})</h4><EvidenceList items={sourceDetail.evidence_spans?.map((span) => ({ ...span, evidence_id: span.id, source_title: sourceDetail.title, source_ref: sourceDetail.source_ref, source_type: sourceDetail.source_type }))} /></div>
          </div>
        )}
      </Drawer>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from 'react';
import { Maximize2, Minus, Plus, RotateCcw, Share2 } from 'lucide-react';
import { api, projectPath } from '../lib/api';
import { useApiData } from '../lib/useApi';
import { Badge, Card, Drawer, EmptyState, ErrorPanel, EvidenceList, Loading, StatusPill } from './ui';

const TYPE_ORDER = ['source', 'decision', 'task', 'person', 'risk', 'blocker', 'question', 'state', 'commit', 'issue', 'unfinished', 'next_action', 'reason', 'dependency', 'fact', 'contact', 'unknown'];
const TYPE_COLORS = {
  source: '#3d6cac', decision: '#20a89a', task: '#f59e0b', person: '#8b5cf6', risk: '#ef4444',
  blocker: '#f97316', question: '#0ea5e9', state: '#14b8a6', commit: '#64748b', issue: '#06b6d4',
  unfinished: '#eab308', next_action: '#22c55e', reason: '#a855f7', dependency: '#94a3b8',
  fact: '#6366f1', contact: '#ec4899', unknown: '#475569',
};

function layout(nodes) {
  const groups = new Map();
  nodes.forEach((node) => {
    const type = TYPE_ORDER.includes(node.node_type) ? node.node_type : 'unknown';
    if (!groups.has(type)) groups.set(type, []);
    groups.get(type).push(node);
  });
  const types = TYPE_ORDER.filter((type) => groups.has(type));
  const maxRows = Math.max(1, ...[...groups.values()].map((items) => items.length));
  const width = 1040;
  const height = 600;
  const positions = new Map();
  types.forEach((type, column) => {
    const items = groups.get(type);
    const x = types.length === 1 ? width / 2 : 70 + column * ((width - 140) / (types.length - 1));
    items.forEach((node, row) => {
      const y = maxRows === 1 ? height / 2 : 60 + row * ((height - 120) / (maxRows - 1));
      const jitter = ((node.id.charCodeAt(node.id.length - 1) % 13) - 6) * 1.5;
      positions.set(node.id, { x: x + jitter, y: y + ((row % 2) ? 8 : -8) });
    });
  });
  return { positions, types };
}

export default function GraphExplorer({ projectId }) {
  const timelineQuery = useApiData(() => api.get(projectPath(projectId, '/timeline')), [projectId], { enabled: Boolean(projectId) });
  const timelineDates = useMemo(() => {
    const dates = (timelineQuery.data?.items || []).map((item) => item.valid_from?.slice(0, 10)).filter(Boolean);
    return [...new Set(dates)].sort();
  }, [timelineQuery.data]);
  const [asOf, setAsOf] = useState('');
  const [sliderIndex, setSliderIndex] = useState(0);
  const [nodeFilter, setNodeFilter] = useState('');
  const [selected, setSelected] = useState(null);
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const dragRef = useRef(null);

  useEffect(() => {
    if (!asOf && timelineDates.length) {
      setAsOf(timelineDates[timelineDates.length - 1]);
      setSliderIndex(timelineDates.length - 1);
    }
  }, [asOf, timelineDates]);

  const query = `/graph${asOf || nodeFilter ? '?' : ''}${[asOf ? `as_of=${encodeURIComponent(asOf)}` : '', nodeFilter ? `node_type=${encodeURIComponent(nodeFilter)}` : ''].filter(Boolean).join('&')}`;
  const graphQuery = useApiData(() => api.get(projectPath(projectId, query)), [projectId, query], { enabled: Boolean(projectId) });
  const detailQuery = useApiData(
    () => api.get(projectPath(projectId, `/graph/nodes/${selected.id}`)),
    [projectId, selected?.id],
    { enabled: Boolean(projectId && selected?.id) },
  );

  const nodes = graphQuery.data?.nodes || [];
  const edges = graphQuery.data?.edges || [];
  const { positions, types } = useMemo(() => layout(nodes), [nodes]);
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const visibleEdges = edges.filter((edge) => positions.has(edge.source) && positions.has(edge.target));

  const onPointerDown = (event) => {
    if (event.button !== 0) return;
    dragRef.current = { x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const onPointerMove = (event) => {
    if (!dragRef.current) return;
    setView((current) => ({
      ...current,
      x: dragRef.current.viewX + (event.clientX - dragRef.current.x),
      y: dragRef.current.viewY + (event.clientY - dragRef.current.y),
    }));
  };
  const onPointerUp = () => { dragRef.current = null; };
  const zoom = (delta) => setView((current) => ({ ...current, scale: Math.max(0.55, Math.min(2.1, current.scale + delta)) }));

  if (!projectId) return <EmptyState title="No project selected" description="Choose a project to explore its temporal knowledge graph." />;
  if (graphQuery.loading && !graphQuery.data) return <Loading label="Reconstructing authorised relationships…" />;
  if (graphQuery.error) return <ErrorPanel error={graphQuery.error} onRetry={graphQuery.refresh} />;

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-[260px] flex-1">
            <div className="mb-2 flex items-center justify-between gap-3">
              <label className="label !mb-0">Project state as of</label>
              <Badge tone="navy">{asOf || 'current'}</Badge>
            </div>
            <input
              type="range"
              min={0}
              max={Math.max(0, timelineDates.length - 1)}
              value={sliderIndex}
              onChange={(event) => {
                const index = Number(event.target.value);
                setSliderIndex(index);
                setAsOf(timelineDates[index] || '');
              }}
              className="w-full accent-teal-600"
              disabled={timelineDates.length < 2}
            />
            <div className="mt-1 flex justify-between text-[11px] text-slate-400"><span>{timelineDates[0] || '—'}</span><span>{timelineDates[timelineDates.length - 1] || '—'}</span></div>
          </div>
          <div className="w-56">
            <label className="label">Node type</label>
            <select className="input !py-2" value={nodeFilter} onChange={(event) => setNodeFilter(event.target.value)}>
              <option value="">All authorised nodes</option>
              {TYPE_ORDER.map((type) => <option key={type} value={type}>{type.replace('_', ' ')}</option>)}
            </select>
          </div>
          <div className="flex gap-1">
            <button className="btn-outline !px-2.5 !py-2" onClick={() => zoom(-0.15)} aria-label="Zoom out"><Minus className="h-4 w-4" /></button>
            <button className="btn-outline !px-2.5 !py-2" onClick={() => zoom(0.15)} aria-label="Zoom in"><Plus className="h-4 w-4" /></button>
            <button className="btn-outline !px-2.5 !py-2" onClick={() => setView({ x: 0, y: 0, scale: 1 })} aria-label="Reset view"><RotateCcw className="h-4 w-4" /></button>
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-bold text-navy-900"><Share2 className="h-4 w-4 text-teal-600" /> Interactive temporal graph</div>
          <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">
            <span className="chip">{nodes.length} nodes</span>
            <span className="chip">{edges.length} edges</span>
            <span className="chip">clearance {graphQuery.data?.clearance}</span>
            <span className="chip">{graphQuery.data?.hidden_by_policy?.nodes || 0} nodes hidden by policy</span>
            <span className="chip">{graphQuery.data?.hidden_by_policy?.edges || 0} edges hidden by policy</span>
          </div>
        </div>
        <div className="relative bg-[radial-gradient(circle_at_50%_10%,rgba(32,168,154,0.08),transparent_45%)]">
          <svg
            viewBox="0 0 1100 660"
            className="h-[620px] w-full touch-none select-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerLeave={onPointerUp}
          >
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
              </marker>
              <filter id="nodeShadow" x="-40%" y="-40%" width="180%" height="180%"><feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#0b1a2e" floodOpacity="0.18" /></filter>
            </defs>
            <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
              {visibleEdges.map((edge) => {
                const a = positions.get(edge.source);
                const b = positions.get(edge.target);
                return (
                  <g key={edge.id} className="graph-edge">
                    <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#cbd5e1" strokeWidth={edge.relation === 'depends_on' ? 1.8 : 1.2} markerEnd="url(#arrow)" opacity="0.72" />
                    <title>{edge.relation}: {nodeById.get(edge.source)?.label} → {nodeById.get(edge.target)?.label}</title>
                  </g>
                );
              })}
              {nodes.map((node) => {
                const pos = positions.get(node.id);
                if (!pos) return null;
                const color = TYPE_COLORS[node.node_type] || TYPE_COLORS.unknown;
                const radius = node.node_type === 'decision' ? 13 : node.node_type === 'source' ? 11 : 9;
                return (
                  <g key={node.id} className="graph-node" transform={`translate(${pos.x} ${pos.y})`} onPointerDown={(event) => event.stopPropagation()} onClick={() => setSelected(node)}>
                    <circle r={radius + 5} fill={color} opacity="0.12" />
                    <circle r={radius} fill={color} stroke="white" strokeWidth="2" filter="url(#nodeShadow)" />
                    <text y={radius + 16} textAnchor="middle" fontSize="10" fontWeight="600" fill="#334155">{node.label.length > 24 ? `${node.label.slice(0, 23)}…` : node.label}</text>
                    <title>{node.label} · {node.node_type} · {node.sensitivity}</title>
                  </g>
                );
              })}
            </g>
          </svg>
          <div className="pointer-events-none absolute bottom-3 left-3 rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-[11px] text-slate-500 shadow-panel">
            Drag to pan · use controls to zoom · click a node for original evidence
          </div>
        </div>
        <div className="flex flex-wrap gap-2 border-t border-slate-200 px-4 py-3">
          {types.map((type) => (
            <span key={type} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-50 px-2 py-1 text-[11px] font-medium capitalize text-slate-600">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: TYPE_COLORS[type] }} />{type.replace('_', ' ')}
            </span>
          ))}
        </div>
      </Card>

      <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.label || 'Node evidence'} subtitle={selected ? `${selected.node_type} · ${selected.sensitivity} · valid from ${selected.valid_from?.slice(0, 10)}` : ''} wide>
        {detailQuery.loading && <Loading label="Loading source evidence…" />}
        {detailQuery.error && <ErrorPanel error={detailQuery.error} onRetry={detailQuery.refresh} />}
        {detailQuery.data && (
          <div className="space-y-5">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2"><StatusPill status={detailQuery.data.node.metadata?.verification_status} /><Badge tone="navy">{detailQuery.data.node.node_type}</Badge></div>
              <p className="text-sm leading-relaxed text-navy-900">{detailQuery.data.node.description}</p>
            </div>
            <div>
              <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">Original evidence ({detailQuery.data.evidence_count})</h4>
              <EvidenceList items={detailQuery.data.evidence} />
            </div>
            <div>
              <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">Visible relationships</h4>
              <div className="space-y-2">
                {detailQuery.data.edges.map((edge) => (
                  <div key={edge.id} className="rounded-xl border border-slate-200 px-3 py-2 text-sm"><span className="font-semibold text-teal-700">{edge.relation.replace(/_/g, ' ')}</span><span className="text-slate-500"> · {edge.label}</span></div>
                ))}
                {!detailQuery.data.edges.length && <p className="muted">No authorised relationships at this point in time.</p>}
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}

import { useMemo, type ReactElement } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchEvaluationResults } from '../api/client'
import { EmptyState, ErrorNotice, LoadingState, PageHeader, Panel } from '../components/ui'
import type { EvaluationArm, EvaluationResults, LearningPoint } from '../types'

const armNames: Record<EvaluationArm, string> = {
  A: 'Fixed rules · no memory',
  B: 'Structured database memory',
  C: 'Hindsight customer memory',
}
const armColors: Record<EvaluationArm, string> = {
  A: '#64748b',
  B: '#0f766e',
  C: '#7c3aed',
}

export default function Evaluation() {
  const evaluation = useQuery({
    queryKey: ['evaluation-results'],
    queryFn: fetchEvaluationResults,
    refetchInterval: 3000,
  })

  const data = evaluation.data
  const daysLate = useMemo(() => data ? monthlySeries(data, 'avg_days_late_by_month') : [], [data])
  const warningLead = useMemo(() => data ? monthlySeries(data, 'early_warning_lead_time_by_month') : [], [data])
  const blockerCatch = useMemo(() => data ? averageMetricSeries(data, 'blocker_catch_rate') : [], [data])
  const learning = useMemo(() => data ? learningSeries(data) : [], [data])
  const hasMetrics = daysLate.length > 0 || warningLead.length > 0 || blockerCatch.length > 0 || learning.length > 0

  if (evaluation.isPending) return <LoadingState label="Loading evaluation results…" />
  if (evaluation.isError) return <ErrorNotice message={evaluation.error.message} retry={() => void evaluation.refetch()} />
  if (!data) return <ErrorNotice message="The evaluation endpoint returned no result payload." />

  return (
    <>
      <PageHeader title="Evaluation" description="Compare the fixed-rules, structured-memory and Hindsight arms using the documented test period." />
      {!hasMetrics ? (
        <Panel><EmptyState title="No evaluation results yet" detail="Evaluation metrics will appear here after completed experiment runs are available from the backend." /></Panel>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3">
            <p className="text-xs leading-5 text-blue-900">Simulated evaluation results only. These metrics are not real-world customer outcomes.</p>
            <p className="text-[11px] font-medium text-blue-700">Testing months: {data.test_months.join(', ')} · Seeds: {data.seeds.join(', ')}</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {(['A', 'B', 'C'] as const).map((arm) => (
              <Panel key={arm} className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Arm {arm}</p>
                    <h3 className="mt-1 text-sm font-semibold text-slate-800">{armNames[arm]}</h3>
                  </div>
                  <span className="mt-1 h-2.5 w-2.5 rounded-full" style={{ backgroundColor: armColors[arm] }} />
                </div>
                <div className="mt-5 grid grid-cols-2 gap-3">
                  <MetricSmall label="Avg. days late" value={formatMetric(readAverage(data, arm, 'average_days_late'), ' days')} />
                  <MetricSmall label="Warning lead" value={formatMetric(readAverage(data, arm, 'early_warning_lead_time'), ' days')} />
                  <MetricSmall label="Blocker catch" value={formatPercent(readAverage(data, arm, 'blocker_catch_rate'))} />
                  <MetricSmall label="Test invoices" value={formatCount(readAverage(data, arm, 'invoice_count'))} />
                </div>
              </Panel>
            ))}
          </div>

          {daysLate.length > 0 && (
            <Panel title="Average days late by test month" subtitle="Lower is better · values aggregated across available seeds" className="mt-5">
              <ChartFrame>
                <BarChart data={daysLate} margin={{ top: 10, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke="#eef2f6" vertical={false} />
                  <XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                  <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }} width={36} />
                  <Tooltip />
                  <Legend />
                  {(['A', 'B', 'C'] as const).map((arm) => <Bar key={arm} dataKey={arm} name={`Arm ${arm}`} fill={armColors[arm]} radius={[4, 4, 0, 0]} />)}
                </BarChart>
              </ChartFrame>
            </Panel>
          )}

          {warningLead.length > 0 && (
            <Panel title="Early-warning lead time" subtitle="Days ahead of the simulated payment run · higher is earlier" className="mt-5">
              <ChartFrame>
                <LineChart data={warningLead} margin={{ top: 10, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke="#eef2f6" vertical={false} />
                  <XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                  <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }} width={36} />
                  <Tooltip />
                  <Legend />
                  {(['A', 'B', 'C'] as const).map((arm) => <Line key={arm} type="monotone" dataKey={arm} name={`Arm ${arm}`} stroke={armColors[arm]} strokeWidth={2} dot={{ r: 3 }} connectNulls />)}
                </LineChart>
              </ChartFrame>
            </Panel>
          )}

          {blockerCatch.length > 0 && (
            <Panel title="Blocker catch rate" subtitle="Share of simulated blocker cases detected · higher is better" className="mt-5">
              <ChartFrame>
                <BarChart data={blockerCatch} margin={{ top: 10, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke="#eef2f6" vertical={false} />
                  <XAxis dataKey="arm" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                  <YAxis domain={[0, 1]} tickFormatter={(value: number) => `${Math.round(value * 100)}%`} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }} width={42} />
                  <Tooltip formatter={(value: number) => formatPercent(value)} />
                  <Bar dataKey="catchRate" name="Catch rate" radius={[4, 4, 0, 0]}>
                    {blockerCatch.map((point) => <Cell key={point.key} fill={armColors[point.key]} />)}
                  </Bar>
                </BarChart>
              </ChartFrame>
            </Panel>
          )}

          {learning.length > 0 && (
            <Panel title="Learning curve" subtitle="Known customer facts over the months 1–3 learning period" className="mt-5">
              <ChartFrame>
                <LineChart data={learning} margin={{ top: 10, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke="#eef2f6" vertical={false} />
                  <XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                  <YAxis domain={[0, 1]} tickFormatter={(value: number) => `${Math.round(value * 100)}%`} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }} width={42} />
                  <Tooltip formatter={(value: number) => formatPercent(value)} />
                  <Line type="monotone" dataKey="coverage" name="Arm C coverage" stroke={armColors.C} strokeWidth={2} dot={{ r: 3 }} connectNulls />
                </LineChart>
              </ChartFrame>
            </Panel>
          )}
        </>
      )}
    </>
  )
}

function MetricSmall({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <p className="text-[10px] font-medium text-slate-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-700">{value}</p>
    </div>
  )
}

function ChartFrame({ children }: { children: ReactElement }) {
  return <div className="h-[280px] px-3 py-5 sm:px-6"><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>
}

function readAverage(results: EvaluationResults, arm: EvaluationArm, key: string): number | null {
  const runs = Object.values(results.arms[arm] ?? {})
  const values = runs
    .map((run) => run[key])
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
}

function monthlySeries(results: EvaluationResults, key: string) {
  const months = new Set<string>()
  for (const arm of ['A', 'B', 'C'] as const) {
    for (const run of Object.values(results.arms[arm] ?? {})) {
      const byMonth = run[key]
      if (isNumberRecord(byMonth)) Object.keys(byMonth).forEach((month) => months.add(month))
    }
  }
  return [...months]
    .filter((month) => results.test_months.includes(Number(month)))
    .sort((a, b) => Number(a) - Number(b))
    .map((month) => {
    const point: { month: string; A: number | null; B: number | null; C: number | null } = {
      month: `Month ${month}`,
      A: null,
      B: null,
      C: null,
    }
    for (const arm of ['A', 'B', 'C'] as const) {
      const values = Object.values(results.arms[arm] ?? {})
        .map((run) => {
          const byMonth = run[key]
          return isNumberRecord(byMonth) ? byMonth[month] : undefined
        })
        .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
      point[arm] = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
    }
    return point
  })
}

function averageMetricSeries(results: EvaluationResults, key: string) {
  return (['A', 'B', 'C'] as const)
    .map((arm) => ({ arm: `Arm ${arm}`, catchRate: readAverage(results, arm, key), key: arm }))
    .filter((point): point is { arm: string; catchRate: number; key: EvaluationArm } => point.catchRate !== null)
}

function learningSeries(results: EvaluationResults): LearningPoint[] {
  const points = Object.values(results.arms.C ?? {})
    .flatMap((run) => Array.isArray(run.learning_curve) ? run.learning_curve : [])
    .filter(isLearningPoint)
  const byMonth = new Map<number, LearningPoint[]>()
  points.forEach((point) => byMonth.set(point.month, [...(byMonth.get(point.month) ?? []), point]))
  return [...byMonth.entries()].sort(([a], [b]) => a - b).map(([month, rows]) => {
    const known = rows.reduce((sum, row) => sum + row.known_facts, 0)
    const total = rows.reduce((sum, row) => sum + row.total_facts, 0)
    return { month, known_facts: known, total_facts: total, coverage: total ? known / total : null }
  })
}

function isNumberRecord(value: unknown): value is Record<string, number | null> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    && Object.values(value).every((item) => item === null || typeof item === 'number')
}

function isLearningPoint(value: unknown): value is LearningPoint {
  if (typeof value !== 'object' || value === null) return false
  const point = value as Record<string, unknown>
  return typeof point.month === 'number'
    && typeof point.known_facts === 'number'
    && typeof point.total_facts === 'number'
    && (typeof point.coverage === 'number' || point.coverage === null)
}

function formatMetric(value: number | null, suffix: string): string {
  return value === null ? '—' : `${value.toFixed(1)}${suffix}`
}

function formatPercent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

function formatCount(value: number | null): string {
  return value === null ? '—' : String(Math.round(value))
}

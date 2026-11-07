import { afterEach, describe, expect, it, vi } from 'vitest'
import { advanceSimulation, ApiError, fetchDashboard } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('API client', () => {
  it('fetches the documented dashboard path', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      total_receivable_paise: 250000,
      overdue_paise: 10000,
      at_risk_customers: [],
      pending_drafts: 1,
      blockers_caught_this_month: 2,
    }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchDashboard()).resolves.toMatchObject({
      total_receivable_paise: 250000,
      pending_drafts: 1,
    })
    expect(fetchMock).toHaveBeenCalledWith('/api/dashboard', undefined)
  })

  it('advances simulated time by hours without changing the route contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      clock: '2026-01-01T10:00:00+05:30',
      drafts_created: 0,
      alerts_raised: 0,
    }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(advanceSimulation(0, 10)).resolves.toMatchObject({
      clock: '2026-01-01T10:00:00+05:30',
    })
    expect(fetchMock).toHaveBeenCalledWith('/api/sim/tick?days=0&hours=10', { method: 'POST' })
  })

  it('surfaces FastAPI validation details as a readable error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: [{ loc: ['body', 'amount_paise'], msg: 'Input should be greater than 0' }],
    }), { status: 422 })))

    await expect(fetchDashboard()).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      code: 'VALIDATION_ERROR',
      message: 'amount_paise: Input should be greater than 0',
    } satisfies Partial<ApiError>)
  })

  it('returns an actionable error when the backend cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    await expect(fetchDashboard()).rejects.toMatchObject({
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Unable to reach Munshi. Check your connection and try again.',
    })
  })
})

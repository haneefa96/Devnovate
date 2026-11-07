export function formatPaiseToRupees(paise: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(paise / 100)
}

export function formatDate(date: Date | string): string {
  const dateOnly = typeof date === 'string' ? date.slice(0, 10) : date.toISOString().slice(0, 10)
  const [year, month, day] = dateOnly.split('-').map(Number)
  if (!year || !month || !day) return dateOnly
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(year, month - 1, day)))
}

export function formatDateTime(date: string): string {
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(date))
}

export function formatMoney(paise: number): string {
  return formatPaiseToRupees(paise)
}

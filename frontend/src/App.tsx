import { lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Customers = lazy(() => import('./pages/Customers'))
const CustomerDetail = lazy(() => import('./pages/CustomerDetail'))
const NewInvoice = lazy(() => import('./pages/NewInvoice'))
const Approvals = lazy(() => import('./pages/Approvals'))
const RiskAlerts = lazy(() => import('./pages/RiskAlerts'))
const Simulation = lazy(() => import('./pages/Simulation'))
const Evaluation = lazy(() => import('./pages/Evaluation'))

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/customers" element={<Customers />} />
        <Route path="/customers/:id" element={<CustomerDetail />} />
        <Route path="/invoices/new" element={<NewInvoice />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/risk" element={<RiskAlerts />} />
        <Route path="/simulation" element={<Simulation />} />
        <Route path="/evaluation" element={<Evaluation />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}

export default App

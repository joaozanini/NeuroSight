import { Routes, Route, Link } from 'react-router-dom'
import SessionsListPage from './pages/SessionsListPage'
import SessionDetailPage from './pages/SessionDetailPage'
import ThemeToggle from './components/ThemeToggle'

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-dot" aria-hidden="true" />
          <span className="brand-name">QuestPro</span>
          <span className="brand-sub">Eye-Tracking</span>
        </Link>
        <div className="topbar-right">
          <ThemeToggle />
        </div>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<SessionsListPage />} />
          <Route path="/sessions/:id" element={<SessionDetailPage />} />
        </Routes>
      </main>
    </div>
  )
}

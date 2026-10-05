import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useUnauthorizedRedirect } from './api/useUnauthorizedRedirect'
import AppLayout from './layouts/AppLayout'
import AuthLayout from './layouts/AuthLayout'
import FullscreenLayout from './layouts/FullscreenLayout'
import NotFoundPage from './pages/NotFoundPage'
import PlaceholderPage from './pages/PlaceholderPage'
import { APP_SCREENS, AUTH_SCREENS, FULLSCREEN_SCREENS } from './routes'

// Vitrine dos componentes, só no `npm run dev` (fica fora do build de produção).
const ComponentsPage = import.meta.env.DEV ? lazy(() => import('./pages/dev/ComponentsPage')) : null

export default function App() {
  useUnauthorizedRedirect()

  return (
    <Routes>
      <Route element={<AuthLayout />}>
        {AUTH_SCREENS.map((screen) => (
          <Route key={screen.path} path={screen.path} element={<PlaceholderPage screen={screen} variant="auth" />} />
        ))}
      </Route>

      <Route element={<FullscreenLayout />}>
        {FULLSCREEN_SCREENS.map((screen) => (
          <Route key={screen.path} path={screen.path} element={<PlaceholderPage screen={screen} variant="fullscreen" />} />
        ))}
      </Route>

      <Route element={<AppLayout />}>
        {APP_SCREENS.map((screen) => (
          <Route key={screen.path} path={screen.path} element={<PlaceholderPage screen={screen} />} />
        ))}
        <Route path="/admin" element={<Navigate to="/admin/usuarios" replace />} />
        {ComponentsPage && (
          <Route
            path="/dev/componentes"
            element={
              <Suspense fallback={null}>
                <ComponentsPage />
              </Suspense>
            }
          />
        )}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

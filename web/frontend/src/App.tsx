import { Suspense, lazy } from 'react'
import type { ReactNode } from 'react'
import { Route, Routes } from 'react-router-dom'
import type { Permission } from './api/auth'
import { useUnauthorizedRedirect } from './api/useUnauthorizedRedirect'
import RequireAuth from './auth/RequireAuth'
import RequirePermission from './auth/RequirePermission'
import AppLayout from './layouts/AppLayout'
import AuthLayout from './layouts/AuthLayout'
import FullscreenLayout from './layouts/FullscreenLayout'
import NotFoundPage from './pages/NotFoundPage'
import PlaceholderPage from './pages/PlaceholderPage'
import ProfilePage from './pages/ProfilePage'
import AdminLayout, { AdminIndex } from './pages/admin/AdminLayout'
import AuditPage from './pages/admin/AuditPage'
import PermissionsPage from './pages/admin/PermissionsPage'
import UserFormPage from './pages/admin/UserFormPage'
import UsersPage from './pages/admin/UsersPage'
import PatientDetailPage from './pages/patients/PatientDetailPage'
import PatientFormPage from './pages/patients/PatientFormPage'
import PatientsPage from './pages/patients/PatientsPage'
import StimuliPage from './pages/stimuli/StimuliPage'
import StimulusDetailPage from './pages/stimuli/StimulusDetailPage'
import ForgotPasswordPage from './pages/auth/ForgotPasswordPage'
import LoginPage from './pages/auth/LoginPage'
import SetPasswordPage from './pages/auth/SetPasswordPage'
import { APP_SCREENS, FULLSCREEN_SCREENS } from './routes'

// Vitrine dos componentes, só no `npm run dev` (fica fora do build de produção).
const ComponentsPage = import.meta.env.DEV ? lazy(() => import('./pages/dev/ComponentsPage')) : null

function guarded(permission: Permission, page: ReactNode) {
  return <RequirePermission permission={permission}>{page}</RequirePermission>
}

export default function App() {
  useUnauthorizedRedirect()

  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/esqueci-senha" element={<ForgotPasswordPage />} />
        <Route path="/redefinir-senha" element={<SetPasswordPage kind="reset" />} />
        <Route path="/aceitar-convite" element={<SetPasswordPage kind="invite" />} />
      </Route>

      <Route element={<RequireAuth />}>
        <Route element={<FullscreenLayout />}>
          {FULLSCREEN_SCREENS.map((screen) => (
            <Route key={screen.path} path={screen.path} element={<PlaceholderPage screen={screen} variant="fullscreen" />} />
          ))}
        </Route>

        <Route element={<AppLayout />}>
          {APP_SCREENS.map((screen) => (
            <Route key={screen.path} path={screen.path} element={<PlaceholderPage screen={screen} />} />
          ))}
          <Route path="/perfil" element={<ProfilePage />} />

          <Route path="/pacientes" element={guarded('patients.view', <PatientsPage />)} />
          <Route path="/pacientes/novo" element={guarded('patients.edit', <PatientFormPage />)} />
          <Route path="/pacientes/:patientId" element={guarded('patients.view', <PatientDetailPage />)} />
          <Route path="/pacientes/:patientId/editar" element={guarded('patients.edit', <PatientFormPage />)} />
          <Route path="/estimulos" element={<StimuliPage />} />
          <Route path="/estimulos/:stimulusId" element={<StimulusDetailPage />} />

          <Route path="/admin" element={<AdminIndex />} />
          <Route element={<AdminLayout />}>
            <Route path="/admin/usuarios" element={guarded('admin.users', <UsersPage />)} />
            <Route path="/admin/permissoes" element={guarded('admin.permissions', <PermissionsPage />)} />
            <Route path="/admin/auditoria" element={guarded('admin.audit', <AuditPage />)} />
          </Route>
          <Route path="/admin/usuarios/novo" element={guarded('admin.users', <UserFormPage />)} />
          <Route path="/admin/usuarios/:userId" element={guarded('admin.users', <UserFormPage />)} />

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
      </Route>
    </Routes>
  )
}

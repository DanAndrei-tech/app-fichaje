import { createBrowserRouter, Navigate } from 'react-router'

import { NotFoundPage } from './NotFoundPage.tsx'

// Cada pantalla se carga bajo demanda (lazy loading): el terminal no
// descarga el código del panel de administración, y viceversa.
export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/admin" replace />,
  },
  {
    path: '/clock/:companySlug',
    lazy: async () => {
      const { TerminalPage } = await import('../features/terminal/TerminalPage.tsx')
      return { Component: TerminalPage }
    },
  },
  {
    path: '/admin',
    lazy: async () => {
      const { AdminPage } = await import('../features/admin/AdminPage.tsx')
      return { Component: AdminPage }
    },
  },
  {
    path: '*',
    Component: NotFoundPage,
  },
])

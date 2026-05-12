import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from '@/components/primitives';
import { AppShell } from '@/components/layout/AppShell';
import LoginPage from '@/pages/Login';
import { ProtectedRoute } from '@/pages/ProtectedRoute';
import Settings from '@/pages/Settings';
import Dashboard from '@/pages/Dashboard';
import NewTrade from '@/pages/NewTrade';
import TradeLog from '@/pages/TradeLog';
import Strategies from '@/pages/Strategies';
import StrategyEditor from '@/pages/StrategyEditor';
import Analytics from '@/pages/Analytics';
import WhatIf from '@/pages/WhatIf';
import NotFound from '@/pages/NotFound';
import PrimitivesDemo from '@/pages/PrimitivesDemo';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppShell />}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/trades" element={<TradeLog />} />
                <Route path="/trades/new" element={<NewTrade />} />
                <Route path="/strategies" element={<Strategies />} />
                <Route path="/strategies/:id" element={<StrategyEditor />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/whatif" element={<WhatIf />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/_dev/primitives" element={<PrimitivesDemo />} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
// FIX: Corrected the import for `useAuth` to point to the correct file.
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './hooks/useAuth';
import Layout from './components/Layout';
import LoginPage from './features/auth/LoginPage';
import DashboardPage from './features/dashboard/DashboardPage';
import LoanListPage from './features/loan-origination/LoanListPage';
import LoanDetailsPage from './features/loan-origination/LoanDetailsPage';
import NewLoanPage from './features/loan-origination/NewLoanPage';
import CustomerListPage from './features/customer-mastery/CustomerListPage';
import CustomerProfilePage from './features/customer-mastery/CustomerProfilePage';
import ComplianceMonitoringPage from './features/compliance/ComplianceMonitoringPage';
import AuditReportPage from './features/compliance/AuditReportPage';

const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

const AppContent: React.FC = () => {
  const { isAuthenticated } = useAuth();

  return (
      <HashRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/*"
            element={
              isAuthenticated ? (
                <Layout>
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/loans" element={<LoanListPage />} />
                    <Route path="/loans/new" element={<NewLoanPage />} />
                    <Route path="/loans/:id" element={<LoanDetailsPage />} />
                    <Route path="/customers" element={<CustomerListPage />} />
                    <Route path="/customers/:id" element={<CustomerProfilePage />} />
                    <Route path="/compliance" element={<ComplianceMonitoringPage />} />
                    <Route path="/audit" element={<AuditReportPage />} />
                    <Route path="*" element={<Navigate to="/" />} />
                  </Routes>
                </Layout>
              ) : (
                <Navigate to="/login" />
              )
            }
          />
        </Routes>
      </HashRouter>
  );
};

export default App;
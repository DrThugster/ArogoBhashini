// src/App.js
import React, { lazy, Suspense, useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { Box, Container } from '@mui/material';
import { styled } from '@mui/material/styles';
import axios from 'axios';

// Components
import Header from './components/Header';
import Loader from './components/Loader';
import ErrorBoundary from './components/ErrorBoundary';

// Lazy loaded components
const HomePage = lazy(() => import('./pages/HomePage'));
const UserDetailsForm = lazy(() => import('./pages/UserDetailsForm'));
const ConsultationPage = lazy(() => import('./pages/ConsultationPage'));
const ConsultationSummary = lazy(() => import('./pages/ConsultationSummary'));

// Styled components
const MainContainer = styled(Box)(({ theme }) => ({
  minHeight: '100vh',
  display: 'flex',
  flexDirection: 'column',
  backgroundColor: theme.palette.background.default,
}));

const ContentContainer = styled(Container)(({ theme }) => ({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  padding: theme.spacing(3),
  [theme.breakpoints.down('sm')]: {
    padding: theme.spacing(2),
  },
}));

// Loading states
const loadingStates = {
  home: 'Loading Arogo Telemedicine...',
  details: 'Preparing consultation form...',
  consultation: 'Setting up secure connection...',
  summary: 'Loading consultation summary...'
};

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const navigate = useNavigate();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const checkConsultation = async () => {
      try {
        const consultationId = localStorage.getItem('consultationId');
        
        if (!consultationId) {
          console.log('No consultation ID found, redirecting to home');
          navigate('/', { replace: true });
          return;
        }

        // Verify consultation exists and is active
        const response = await axios.get(
          `${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/consultation/status/${consultationId}`
        );

        if (response.data.status !== 'active') {
          console.log('Consultation is not active, redirecting to home');
          localStorage.removeItem('consultationId');
          navigate('/', { replace: true });
          return;
        }

        setIsChecking(false);
      } catch (error) {
        console.error('Error verifying consultation:', error);
        localStorage.removeItem('consultationId');
        navigate('/', { replace: true });
      }
    };

    checkConsultation();
  }, [navigate]);

  if (isChecking) {
    return <Loader message="Verifying consultation..." />;
  }

  return children;
};

// Main App Component
const App = () => {
  // Handle global errors
  const handleError = (error) => {
    console.error('Global error:', error);
    // You could add global error handling here
  };

  return (
    <Router>
      <MainContainer>
        <Header />
        <ContentContainer maxWidth="lg">
          <ErrorBoundary onError={handleError}>
            <Routes>
              {/* Home Page */}
              <Route 
                path="/" 
                element={
                  <Suspense fallback={<Loader message={loadingStates.home} />}>
                    <HomePage />
                  </Suspense>
                } 
              />

              {/* User Details Form */}
              <Route 
                path="/consultation/details" 
                element={
                  <Suspense fallback={<Loader message={loadingStates.details} />}>
                    <UserDetailsForm />
                  </Suspense>
                } 
              />

              {/* Active Consultation */}
              <Route 
                path="/consultation/chat/:consultationId" 
                element={
                  <ErrorBoundary>
                    <ProtectedRoute>
                      <Suspense fallback={<Loader message={loadingStates.consultation} />}>
                        <ConsultationPage />
                      </Suspense>
                    </ProtectedRoute>
                  </ErrorBoundary>
                } 
              />

              {/* Consultation Summary */}
              <Route 
                path="/consultation/summary/:consultationId" 
                element={
                  <ErrorBoundary>
                    <ProtectedRoute>
                      <Suspense fallback={<Loader message={loadingStates.summary} />}>
                        <ConsultationSummary />
                      </Suspense>
                    </ProtectedRoute>
                  </ErrorBoundary>
                } 
              />

              {/* Catch all other routes */}
              <Route 
                path="*" 
                element={<Navigate to="/" replace />} 
              />
            </Routes>
          </ErrorBoundary>
        </ContentContainer>
      </MainContainer>
    </Router>
  );
};

export default App;
// src/components/ErrorBoundary.js
import React from 'react';
import { Alert, Button, Container, Typography } from '@mui/material';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Container maxWidth="md" sx={{ mt: 4 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            <Typography variant="h6">Something went wrong</Typography>
            <Typography>{this.state.error?.message}</Typography>
          </Alert>
          <Button
            variant="contained"
            onClick={() => window.location.href = '/'}
            sx={{ mt: 2 }}
          >
            Return Home
          </Button>
        </Container>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
// frontend/src/pages/HomePage.js
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Container, 
  Box, 
  Typography, 
  Button, 
  Paper 
} from '@mui/material';
import { styled } from '@mui/material/styles';
import MedicalServicesIcon from '@mui/icons-material/MedicalServices';

const StyledPaper = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(4),
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: theme.spacing(3),
  maxWidth: 600,
  margin: 'auto',
  marginTop: theme.spacing(8),
  background: 'rgba(255, 255, 255, 0.9)',
  backdropFilter: 'blur(10px)',
}));

const AnimatedButton = styled(Button)`
  transition: transform 0.3s ease-in-out;
  &:hover {
    transform: scale(1.05);
  }
`;

const HomePage = () => {
  const navigate = useNavigate();

  return (
    <Container>
      <StyledPaper elevation={3}>
        <MedicalServicesIcon sx={{ fontSize: 60, color: 'primary.main' }} />
        
        <Typography variant="h4" component="h1" gutterBottom>
          Welcome to Arogo Telemedicine
        </Typography>
        
        <Typography variant="body1" align="center" color="text.secondary" paragraph>
          Get instant medical pre-diagnosis using our AI-powered consultation system.
          Start your consultation now to receive personalized health insights.
        </Typography>

        <Box sx={{ mt: 3 }}>
          <AnimatedButton
            variant="contained"
            size="large"
            color="primary"
            onClick={() => navigate('/consultation/details')}
            sx={{ px: 4, py: 1.5 }}
          >
            Start Consultation
          </AnimatedButton>
        </Box>
        
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Available 24/7 • Secure • Confidential
        </Typography>
      </StyledPaper>
    </Container>
  );
};

export default HomePage;
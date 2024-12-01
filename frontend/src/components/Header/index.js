// src/components/Header/index.js
import React from 'react';
import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import LocalHospitalIcon from '@mui/icons-material/LocalHospital';

const Header = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const isHomePage = location.pathname === '/';

  return (
    <AppBar position="static" elevation={2}>
      <Toolbar>
        <Box 
          sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            cursor: 'pointer' 
          }}
          onClick={() => navigate('/')}
        >
          <LocalHospitalIcon sx={{ mr: 1 }} />
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Arogo Telemedicine
          </Typography>
        </Box>
        
        <Box sx={{ flexGrow: 1 }} />
        
        {!isHomePage && (
          <Button 
            color="inherit"
            onClick={() => navigate('/')}
          >
            New Consultation
          </Button>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Header;
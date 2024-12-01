// src/components/Loader/index.js
import React from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import { styled } from '@mui/material/styles';

const LoaderContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  minHeight: '200px',
  gap: theme.spacing(2)
}));

const Loader = ({ message = 'Loading...' }) => {
  return (
    <LoaderContainer>
      <CircularProgress />
      <Typography variant="body2" color="textSecondary">
        {message}
      </Typography>
    </LoaderContainer>
  );
};

export default Loader;
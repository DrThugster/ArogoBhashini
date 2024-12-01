// src/styles/ChatStyles.js
import { styled } from '@mui/material/styles';
import { Box } from '@mui/material';

export const ChatContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  position: 'relative',
}));

export const MessageTime = styled(Box)(({ theme }) => ({
  fontSize: '0.75rem',
  color: theme.palette.text.secondary,
  marginTop: theme.spacing(0.5),
}));

export const SystemMessage = styled(Box)(({ theme }) => ({
  textAlign: 'center',
  color: theme.palette.text.secondary,
  margin: theme.spacing(1, 0),
  fontSize: '0.875rem',
}));
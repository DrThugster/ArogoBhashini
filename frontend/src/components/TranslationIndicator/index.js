// src/components/TranslationIndicator/index.js
import React from 'react';
import { 
  Box, 
  Typography, 
  IconButton, 
  Tooltip, 
  Chip,
  Collapse,
  Paper
} from '@mui/material';
import { styled } from '@mui/material/styles';
import TranslateIcon from '@mui/icons-material/Translate';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { getLanguageName } from '../../utils/helpers';
import ConfidenceIndicator from '../ChatInterface/ConfidenceIndicator';

const StyledPaper = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(1),
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(1),
  backgroundColor: theme.palette.grey[50],
}));

const LanguageChip = styled(Chip)(({ theme, active }) => ({
  backgroundColor: active ? theme.palette.primary.light : theme.palette.grey[200],
  color: active ? theme.palette.primary.contrastText : theme.palette.text.primary,
}));

const TranslationIndicator = ({
  sourceLanguage,
  targetLanguage,
  confidence,
  showOriginal,
  onToggle,
  size = 'medium'
}) => {
  return (
    <StyledPaper elevation={0}>
      {/* Source Language */}
      <LanguageChip
        label={getLanguageName(sourceLanguage, sourceLanguage)}
        size={size}
        active={showOriginal}
      />

      {/* Translation Direction */}
      <IconButton size="small" onClick={onToggle}>
        <SwapHorizIcon fontSize={size} />
      </IconButton>

      {/* Target Language */}
      <LanguageChip
        label={getLanguageName(targetLanguage, targetLanguage)}
        size={size}
        active={!showOriginal}
      />

      {/* Confidence Score */}
      <ConfidenceIndicator
        confidence={confidence}
        type="translation"
        sourceLanguage={sourceLanguage}
        targetLanguage={targetLanguage}
        showLanguages
        size={size === 'small' ? 24 : 32}
      />

      {/* Translation Icon */}
      <Tooltip title="Translation powered by Bhashini">
        <TranslateIcon fontSize={size} color="action" />
      </Tooltip>
    </StyledPaper>
  );
};

export default TranslationIndicator;
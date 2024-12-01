// src/components/LanguageSelector/index.js
import React from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Tooltip,
  IconButton,
} from '@mui/material';
import TranslateIcon from '@mui/icons-material/Translate';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import InfoIcon from '@mui/icons-material/Info';

const SUPPORTED_LANGUAGES = {
  en: {
    name: 'English',
    native: 'English',
    direction: 'ltr'
  },
  hi: {
    name: 'Hindi',
    native: 'हिंदी',
    direction: 'ltr'
  },
  ta: {
    name: 'Tamil',
    native: 'தமிழ்',
    direction: 'ltr'
  },
  te: {
    name: 'Telugu',
    native: 'తెలుగు',
    direction: 'ltr'
  },
  ml: {
    name: 'Malayalam',
    native: 'മലയാളം',
    direction: 'ltr'
  },
  kn: {
    name: 'Kannada',
    native: 'ಕನ್ನಡ',
    direction: 'ltr'
  },
  bn: {
    name: 'Bengali',
    native: 'বাংলা',
    direction: 'ltr'
  }
};

const LanguageSelector = ({
  selectedLanguage,
  onLanguageChange,
  autoDetect,
  onAutoDetectChange,
  detectedLanguage,
  confidence
}) => {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      <FormControl size="small" sx={{ minWidth: 120 }}>
        <InputLabel>Language</InputLabel>
        <Select
          value={selectedLanguage}
          onChange={(e) => onLanguageChange(e.target.value)}
          label="Language"
          disabled={autoDetect}
        >
          {Object.entries(SUPPORTED_LANGUAGES).map(([code, lang]) => (
            <MenuItem key={code} value={code}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <span>{lang.native}</span>
                <span style={{ color: 'text.secondary', fontSize: '0.8em' }}>
                  ({lang.name})
                </span>
              </Box>
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <FormControlLabel
        control={
          <Switch
            checked={autoDetect}
            onChange={(e) => onAutoDetectChange(e.target.checked)}
            color="primary"
          />
        }
        label="Auto Detect"
      />

      {detectedLanguage && autoDetect && (
        <Tooltip title={`Detected language: ${SUPPORTED_LANGUAGES[detectedLanguage]?.name || detectedLanguage} (${Math.round(confidence * 100)}% confidence)`}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <AutorenewIcon color="primary" fontSize="small" />
            <span>{SUPPORTED_LANGUAGES[detectedLanguage]?.native || detectedLanguage}</span>
          </Box>
        </Tooltip>
      )}

      <Tooltip title="Language support powered by Bhashini">
        <IconButton size="small">
          <InfoIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
};

export default LanguageSelector;
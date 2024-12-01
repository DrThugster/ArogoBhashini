// src/components/ChatInterface/ConfidenceIndicator.js
import React from 'react';
import { Box, Typography, CircularProgress, Tooltip, Badge } from '@mui/material';
import { styled } from '@mui/material/styles';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import TranslateIcon from '@mui/icons-material/Translate';
import LocalHospitalIcon from '@mui/icons-material/LocalHospital';
import { getLanguageName } from '../../utils/helpers';

const IndicatorWrapper = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(1),
}));

const ConfidenceCircle = styled(Box)(({ theme }) => ({
  position: 'relative',
  display: 'inline-flex',
  alignItems: 'center',
}));

const ConfidenceValue = styled(Typography)(({ theme, confidence }) => ({
  position: 'absolute',
  left: '50%',
  top: '50%',
  transform: 'translate(-50%, -50%)',
  fontSize: '0.75rem',
  fontWeight: 'bold',
  color: confidence >= 70 ? theme.palette.success.main :
         confidence >= 40 ? theme.palette.warning.main :
         theme.palette.error.main,
}));

const ConfidenceIndicator = ({ 
  confidence, 
  size = 40, 
  type = 'general', // 'general', 'translation', 'medical'
  sourceLanguage,
  targetLanguage,
  showLanguages = false
}) => {
  const getConfidenceColor = (score) => {
    if (score >= 70) return 'success';
    if (score >= 40) return 'warning';
    return 'error';
  };

  const getConfidenceIcon = (score, type) => {
    const icon = score >= 70 ? <CheckCircleOutlineIcon color="success" /> :
                score >= 40 ? <WarningAmberIcon color="warning" /> :
                <ErrorOutlineIcon color="error" />;

    if (type === 'translation') {
      return <Badge badgeContent={<TranslateIcon fontSize="small" />}>{icon}</Badge>;
    }
    if (type === 'medical') {
      return <Badge badgeContent={<LocalHospitalIcon fontSize="small" />}>{icon}</Badge>;
    }
    return icon;
  };

  const getTooltipText = (score, type) => {
    const baseText = score >= 70 ? 'High confidence' :
                    score >= 40 ? 'Moderate confidence' :
                    'Low confidence';

    if (type === 'translation' && showLanguages) {
      return `${baseText} in translation from ${getLanguageName(sourceLanguage)} to ${getLanguageName(targetLanguage)}`;
    }
    if (type === 'medical') {
      return `${baseText} in medical analysis`;
    }
    return `${baseText} in response`;
  };

  return (
    <Tooltip title={getTooltipText(confidence, type)} arrow>
      <IndicatorWrapper>
        <ConfidenceCircle>
          <CircularProgress
            variant="determinate"
            value={confidence}
            size={size}
            color={getConfidenceColor(confidence)}
          />
          <ConfidenceValue confidence={confidence}>
            {Math.round(confidence)}%
          </ConfidenceValue>
        </ConfidenceCircle>
        {getConfidenceIcon(confidence, type)}
      </IndicatorWrapper>
    </Tooltip>
  );
};

export default ConfidenceIndicator;
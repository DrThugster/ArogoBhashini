// src/components/ChatInterface/MessageBubble.js
import React, { useState } from 'react';
import { Paper, Typography, Box, IconButton, Tooltip, Chip, Collapse } from '@mui/material';
import { styled } from '@mui/material/styles';
import LocalHospitalIcon from '@mui/icons-material/LocalHospital';
import { getLanguageName, getTextDirection } from '../../utils/helpers';
import TranslationIndicator from '../TranslationIndicator';
import AudioControls from '../AudioControls';
import ConfidenceIndicator from './ConfidenceIndicator';

const MessageContainer = styled(Box)(({ theme, dir }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: props => props.isUser ? 'flex-end' : 'flex-start',
  marginBottom: theme.spacing(1),
  width: '100%',
  direction: dir
}));

const StyledPaper = styled(Paper)(({ theme, isUser }) => ({
  padding: theme.spacing(2),
  maxWidth: '70%',
  backgroundColor: isUser ? theme.palette.primary.main : theme.palette.grey[100],
  color: isUser ? theme.palette.primary.contrastText : theme.palette.text.primary,
  borderRadius: theme.spacing(2),
  borderTopRightRadius: isUser ? theme.spacing(0) : theme.spacing(2),
  borderTopLeftRadius: isUser ? theme.spacing(2) : theme.spacing(0),
}));

const MessageMeta = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(1),
  marginTop: theme.spacing(0.5),
  fontSize: '0.75rem',
  color: theme.palette.text.secondary,
  flexWrap: 'wrap'
}));

const EmergencyBadge = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(0.5),
  color: theme.palette.error.main,
  backgroundColor: theme.palette.error.light,
  padding: theme.spacing(0.5, 1),
  borderRadius: theme.spacing(1),
  marginTop: theme.spacing(1),
}));

const MessageBubble = ({ 
  message, 
  interfaceLanguage = 'en',
  onVoicePreferenceChange,
  onLanguageChange 
}) => {
  const [showOriginal, setShowOriginal] = useState(false);
  const [showControls, setShowControls] = useState(false);
  
  const isUser = message.type === 'user';
  const textDirection = getTextDirection(message.language?.target);
  
  const hasTranslation = message.originalContent !== message.content;
  const displayText = showOriginal ? message.originalContent : message.content;

  // Emergency warning texts in different languages
  const emergencyText = {
    en: "This requires immediate medical attention",
    hi: "इसे तत्काल चिकित्सा देखभाल की आवश्यकता है",
    // Add more languages as needed
  }[interfaceLanguage] || emergencyText.en;

  return (
    <MessageContainer isUser={isUser} dir={textDirection}>
      {/* Translation Indicator if message is translated */}
      {hasTranslation && (
        <TranslationIndicator
          sourceLanguage={message.language.source}
          targetLanguage={message.language.target}
          confidence={message.translation?.confidence}
          showOriginal={showOriginal}
          onToggle={() => setShowOriginal(!showOriginal)}
          size="small"
        />
      )}

      {/* Message Content */}
      <StyledPaper isUser={isUser} elevation={1}>
        <Typography variant="body1" dir={textDirection}>
          {displayText}
        </Typography>

        {/* Medical Analysis */}
        {message.analysis?.symptoms?.length > 0 && (
          <Box sx={{ mt: 1 }}>
            {message.analysis.symptoms.map((symptom, index) => (
              <Chip
                key={index}
                label={symptom.name}
                size="small"
                variant="outlined"
                sx={{ mr: 0.5, mb: 0.5 }}
              />
            ))}
          </Box>
        )}

        {/* Emergency Warning */}
        {message.analysis?.requiresEmergency && (
          <EmergencyBadge>
            <LocalHospitalIcon fontSize="small" color="error" />
            <Typography variant="caption" color="error">
              {emergencyText}
            </Typography>
          </EmergencyBadge>
        )}
      </StyledPaper>

      {/* Message Metadata */}
      <MessageMeta>
        {/* Language Indicator */}
        <Tooltip title={`${getLanguageName(message.language?.target, interfaceLanguage)}`}>
          <Chip
            size="small"
            label={message.language?.target || 'en'}
            variant="outlined"
          />
        </Tooltip>

        {/* Confidence Indicators */}
        {message.analysis?.confidence && (
          <ConfidenceIndicator
            confidence={message.analysis.confidence}
            type="medical"
            size="small"
          />
        )}

        {hasTranslation && message.translation?.confidence && (
          <ConfidenceIndicator
            confidence={message.translation.confidence}
            type="translation"
            sourceLanguage={message.language.source}
            targetLanguage={message.language.target}
            size="small"
          />
        )}

        {/* Audio Toggle */}
        {message.audio && (
          <Chip
            size="small"
            label={interfaceLanguage === 'en' ? 'Audio Available' : 'ऑडियो उपलब्ध है'}
            onClick={() => setShowControls(!showControls)}
            variant="outlined"
            color="primary"
          />
        )}
      </MessageMeta>

      {/* Audio Controls */}
      <Collapse in={showControls && message.audio}>
        <Box sx={{ mt: 1, maxWidth: '100%' }}>
          <AudioControls
            audioUrl={message.audio}
            language={message.language.target}
            voiceGender={message.voice?.gender || 'female'}
            onVoiceChange={onVoicePreferenceChange}
            interfaceLanguage={interfaceLanguage}
          />
        </Box>
      </Collapse>
    </MessageContainer>
  );
};

export default MessageBubble;
// src/utils/helpers.js
import { SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE } from './languageMetadata';

// Keep original functions
export const formatDate = (date, language = DEFAULT_LANGUAGE) => {
  return new Date(date).toLocaleString(getLanguageLocale(language));
};

export const getSeverityColor = (score) => {
  if (score <= 3) return '#4caf50'; // Green
  if (score <= 7) return '#ff9800'; // Orange
  return '#f44336'; // Red
};

export const getConfidenceLabel = (score, language = DEFAULT_LANGUAGE) => {
  const labels = {
    en: {
      high: 'High',
      medium: 'Medium',
      low: 'Low'
    },
    hi: {
      high: 'उच्च',
      medium: 'मध्यम',
      low: 'निम्न'
    }
    // Add more language translations as needed
  };

  const selectedLabels = labels[language] || labels[DEFAULT_LANGUAGE];
  
  if (score >= 80) return selectedLabels.high;
  if (score >= 50) return selectedLabels.medium;
  return selectedLabels.low;
};

export const downloadBlob = (blob, fileName) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', fileName);
  document.body.appendChild(link);
  link.click();
  link.parentNode.removeChild(link);
  window.URL.revokeObjectURL(url);
};

export const formatAudioDuration = (seconds) => {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
};

export const validateEmail = (email) => {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
};

export const validateMobile = (mobile) => {
  const re = /^\+?[\d\s-]{10,}$/;
  return re.test(mobile);
};

export const generateConsultationId = () => {
  return 'cons-' + Math.random().toString(36).substr(2, 9);
};

// New language-specific helper functions
export const getLanguageLocale = (languageCode) => {
  const language = SUPPORTED_LANGUAGES[languageCode];
  return language ? `${languageCode}-${language.region}` : 'en-US';
};

export const getTextDirection = (languageCode) => {
  return SUPPORTED_LANGUAGES[languageCode]?.direction || 'ltr';
};

export const formatNumber = (number, language = DEFAULT_LANGUAGE) => {
  return new Intl.NumberFormat(getLanguageLocale(language)).format(number);
};

export const getLanguageName = (languageCode, displayLanguage = DEFAULT_LANGUAGE) => {
  const language = SUPPORTED_LANGUAGES[languageCode];
  return displayLanguage === languageCode ? language?.native : language?.name;
};

export const detectTextDirection = (text) => {
  const rtlChars = /[\u0591-\u07FF\u200F\u202B\u202E\uFB1D-\uFDFD\uFE70-\uFEFC]/;
  return rtlChars.test(text) ? 'rtl' : 'ltr';
};

export const formatMessageTimestamp = (date, language = DEFAULT_LANGUAGE) => {
  return new Intl.DateTimeFormat(getLanguageLocale(language), {
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(date));
};

export const getVoiceLanguageCode = (languageCode) => {
  const language = SUPPORTED_LANGUAGES[languageCode];
  return language?.supported.tts ? languageCode : DEFAULT_LANGUAGE;
};

export const sanitizeLanguageCode = (languageCode) => {
  return SUPPORTED_LANGUAGES[languageCode] ? languageCode : DEFAULT_LANGUAGE;
};
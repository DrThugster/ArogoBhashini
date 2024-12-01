// src/pages/ConsultationPage.js
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import {
  Container,
  Paper,
  Box,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Drawer,
  IconButton,
  Divider,
  FormControl,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Tooltip,
  Badge
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import TranslateIcon from '@mui/icons-material/Translate';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import InfoIcon from '@mui/icons-material/Info';
import CloseIcon from '@mui/icons-material/Close';
import ChatInterface from '../components/ChatInterface';
import { SUPPORTED_LANGUAGES, VOICE_OPTIONS } from '../utils/languageMetadata';
import { getTextDirection } from '../utils/helpers';
import { getTranslation } from '../utils/translations';
import axios from 'axios';
import { getConsultationStatus } from '../redux/slices/consultationSlice'; // Add this import

const ConsultationPage = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { consultationId } = useParams();
  
  // Get consultation state from Redux
  const consultation = useSelector(state => state.consultation);

  const [error, setError] = useState(null);

  // Language and Voice Settings
  const [settings, setSettings] = useState({
    showSettings: false,
    interfaceLanguage: 'en',
    preferredLanguage: 'en',
    autoDetectLanguage: true,
    voice: {
      enabled: true,
      gender: 'female',
      speed: 1
    }
  });

  // Simplify the consultation fetching
  useEffect(() => {
    if (consultationId) {
      dispatch(getConsultationStatus(consultationId));
    }
  }, [consultationId, dispatch]);

  // Load saved preferences
  useEffect(() => {
    const savedPreferences = JSON.parse(localStorage.getItem('userLanguagePreferences'));
    if (savedPreferences) {
      setSettings(prev => ({
        ...prev,
        interfaceLanguage: savedPreferences.interface || 'en',
        preferredLanguage: savedPreferences.preferred || 'en',
        autoDetectLanguage: savedPreferences.autoDetect ?? true,
        voice: savedPreferences.voice || prev.voice
      }));
    }
  }, []);

  useEffect(() => {
    const fetchConsultationData = async () => {
      if (consultationId) {
        try {
          // Get data directly from the Redux action
          const result = await dispatch(getConsultationStatus(consultationId)).unwrap();
          
          // Update settings with language preferences
          if (result && result.language_preferences) {
            setSettings(prev => ({
              ...prev,
              preferredLanguage: result.language_preferences.preferred || prev.preferredLanguage,
              interfaceLanguage: result.language_preferences.interface || prev.interfaceLanguage
            }));
          }
        } catch (err) {
          console.error('Error fetching consultation:', err);
        }
      }
    };

    fetchConsultationData();
  }, [consultationId, dispatch]);

  const handleEndConsultation = async () => {
    try {
      await axios.get(`http://localhost:8000/api/consultation/summary/${consultationId}`);
      navigate(`/consultation/summary/${consultationId}`);
    } catch (err) {
      setError('Failed to end consultation. Please try again.');
    }
  };

  // Settings handlers
  const handleSettingChange = (setting, value) => {
    setSettings(prev => {
      const newSettings = {
        ...prev,
        [setting]: value
      };
      // Save to localStorage
      localStorage.setItem('userLanguagePreferences', JSON.stringify({
        interface: newSettings.interfaceLanguage,
        preferred: newSettings.preferredLanguage,
        autoDetect: newSettings.autoDetectLanguage,
        voice: newSettings.voice
      }));
      return newSettings;
    });
  };

  const getTranslatedText = (key) => {
    return getTranslation(key, settings.interfaceLanguage);
  };

   // Show loading state while fetching
   if (consultation.loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  // Show error state if there's an error
  if (consultation.error) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {consultation.error}
        </Alert>
        <Button variant="contained" onClick={() => navigate('/')}>
          Return Home
        </Button>
      </Container>
    );
  }

  // Show warning if no consultation data
  if (!consultation.userDetails) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Alert severity="warning">
          No consultation data found
        </Alert>
      </Container>
    );
  }

  return (
    <Container 
      maxWidth="md" 
      sx={{ py: 4 }}
      dir={getTextDirection(settings.interfaceLanguage)}
    >
      <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">
            Consultation {consultationId}
          </Typography>
          {/* User details from Redux store */}
          {consultation.userDetails && (
            <Typography variant="body2" color="text.secondary">
              {`${consultation.userDetails.first_name} ${consultation.userDetails.last_name}`}
            </Typography>
          )}
        </Box>

        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">
          {getTranslation('title', settings.interfaceLanguage)}
          </Typography>
          
          <Box display="flex" gap={1}>
           <Tooltip title={getTranslation('settings', settings.interfaceLanguage)}>
              <IconButton onClick={() => handleSettingChange('showSettings', true)}>
                <SettingsIcon />
              </IconButton>
            </Tooltip>
            
            <Button
              variant="contained"
              color="primary"
              onClick={handleEndConsultation}
            >
              {getTranslation('endConsultation', settings.interfaceLanguage)}
            </Button>
          </Box>
        </Box>
        
        {consultation && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary">
            {`${getTranslation('patientDetails', settings.interfaceLanguage)}: ${consultation.userDetails.firstName} ${consultation.userDetails.lastName}`}
            </Typography>
          </Box>
        )}
      </Paper>

      <ChatInterface
        consultationId={consultationId}
        onError={(error) => setError(error)}
        settings={settings}
        onSettingChange={handleSettingChange}
      />

      {/* Settings Drawer */}
      <Drawer
        anchor="right"
        open={settings.showSettings}
        onClose={() => handleSettingChange('showSettings', false)}
      >
        <Box sx={{ width: 300, p: 3 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              {getTranslation('settings', settings.interfaceLanguage)}
            </Typography>
            <IconButton onClick={() => handleSettingChange('showSettings', false)}>
              <CloseIcon />
            </IconButton>
          </Box>

          <Divider sx={{ mb: 2 }} />

          {/* Language Settings */}
          <Typography variant="subtitle2" gutterBottom>
            {getTranslation('languageSettings', settings.interfaceLanguage)}
          </Typography>
          
          <FormControl fullWidth margin="normal">
            <Typography variant="caption">
              {getTranslation('interfaceLanguage', settings.interfaceLanguage)}
            </Typography>
            <Select
              size="small"
              value={settings.interfaceLanguage}
              onChange={(e) => handleSettingChange('interfaceLanguage', e.target.value)}
            >
              {Object.entries(SUPPORTED_LANGUAGES).map(([code, lang]) => (
                <MenuItem key={code} value={code}>
                  {`${lang.native} (${lang.name})`}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth margin="normal">
            <Typography variant="caption">
              {getTranslation('preferredLanguage', settings.interfaceLanguage)}
            </Typography>
            <Select
              size="small"
              value={settings.preferredLanguage}
              onChange={(e) => handleSettingChange('preferredLanguage', e.target.value)}
            >
              {Object.entries(SUPPORTED_LANGUAGES).map(([code, lang]) => (
                <MenuItem key={code} value={code}>
                  {`${lang.native} (${lang.name})`}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControlLabel
            control={
              <Switch
                checked={settings.autoDetectLanguage}
                onChange={(e) => handleSettingChange('autoDetectLanguage', e.target.checked)}
              />
            }
            label={getTranslation('autoDetect', settings.interfaceLanguage)}
          />

          <Divider sx={{ my: 2 }} />

          {/* Voice Settings */}
          <Typography variant="subtitle2" gutterBottom>
            {getTranslation('voiceSettings', settings.interfaceLanguage)}
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={settings.voice.enabled}
                onChange={(e) => handleSettingChange('voice', {
                  ...settings.voice,
                  enabled: e.target.checked
                })}
              />
            }
            label={getTranslation('enableVoice', settings.interfaceLanguage)}
          />

          {settings.voice.enabled && (
            <FormControl fullWidth margin="normal">
              <Typography variant="caption">
                {getTranslation('voiceGender', settings.interfaceLanguage)}
              </Typography>
              <Select
                size="small"
                value={settings.voice.gender}
                onChange={(e) => handleSettingChange('voice', {
                  ...settings.voice,
                  gender: e.target.value
                })}
              >
                {VOICE_OPTIONS.genders.map(gender => (
                  <MenuItem key={gender} value={gender}>
                    {getTranslation(gender, settings.interfaceLanguage)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
        </Box>
      </Drawer>
    </Container>
  );
};

export default ConsultationPage;
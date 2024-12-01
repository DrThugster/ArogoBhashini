// src/pages/UserDetailsForm.js

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { startConsultation } from '../redux/slices/consultationSlice';
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Grid,
  MenuItem,
  Box,
  CircularProgress,
  Alert,
  FormControl,
  FormControlLabel,
  Switch,
  Select,
  InputLabel,
  Divider
} from '@mui/material';
import { SUPPORTED_LANGUAGES, VOICE_OPTIONS } from '../utils/languageMetadata';
import { getTextDirection } from '../utils/helpers';
import { getLanguageName } from '../utils/languageMetadata';

const UserDetailsForm = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    age: '',
    gender: '',
    height: '',
    weight: '',
    email: '',
    mobile: '',
    languagePreferences: {
        language: 'en',
        enable_auto_detect: true
    },
    voice_preferences: {
        enabled: true,
        gender: 'female',
        speed: 1.0
    }
});

  const getFieldLabel = (key) => {

    if (!key) return '';

    // Remove any trailing asterisks or spaces from the key
    const cleanKey = key.replace(/\s*\*\s*$/, '');
    return getLanguageName(formData.languagePreferences.language, cleanKey);
  };

  // Initialize with browser language if supported
  useEffect(() => {
    const browserLang = navigator.language.split('-')[0];
    if (SUPPORTED_LANGUAGES[browserLang]) {
      setFormData(prev => ({
        ...prev,
        languagePreferences: { ...prev.languagePreferences, language: browserLang }
      }));
    }
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (name.startsWith('voice_preferences')) {
      setFormData(prev => ({
        ...prev,
        voice_preferences: {
          ...prev.voice_preferences,
          [name.split('.')[1]]: name.endsWith('enabled') ? e.target.checked : value
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [name]: value
      }));
    }
  };

  const handleLanguageChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      languagePreferences: {
        ...prev.languagePreferences,
        [name]: value
      }
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Format data according to backend expectations
      const formattedData = {
        first_name: formData.firstName,
        last_name: formData.lastName,
        age: parseInt(formData.age),
        gender: formData.gender.toLowerCase(),
        email: formData.email,
        mobile: formData.mobile,
        vitals: {
          height: parseFloat(formData.height),
          weight: parseFloat(formData.weight)
        },
        language_preferences: {
          preferred: formData.languagePreferences.language,
          interface: formData.languagePreferences.language,
          auto_detect: formData.languagePreferences.enable_auto_detect
        },
        device_info: {
          platform: navigator.platform,
          userAgent: navigator.userAgent
        },
        session_metadata: {
          timestamp: new Date().toISOString(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        }
      };

      console.log('Submitting formatted data:', formattedData);

      const result = await dispatch(startConsultation(formattedData)).unwrap();

      if (result?.consultation_id) {
        // Store necessary data in localStorage
        localStorage.setItem('consultationId', result.consultation_id);
        localStorage.setItem('userLanguagePreferences', JSON.stringify({
          preferred: formData.languagePreferences.language,
          interface: formData.languagePreferences.language,
          auto_detect: formData.languagePreferences.enable_auto_detect
        }));

        navigate(`/consultation/chat/${result.consultation_id}`);
      } else {
        throw new Error('Invalid response from server');
      }
    } catch (err) {
      console.error('Consultation creation error:', err);
      setError(typeof err === 'string' ? err : 'Failed to start consultation. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const formDirection = getTextDirection(formData.languagePreferences.language);

  return (
    <Container maxWidth="md">
      <Paper elevation={3} sx={{ p: 4, mt: 4 }}>
        <Typography variant="h5" component="h2" gutterBottom align="center" dir={formDirection}>
          {getLanguageName(formData.languagePreferences.language, 'Patient Details')}
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit} dir={formDirection}>
          <Grid container spacing={3}>
            {/* Personal Details Section */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                {getFieldLabel('Personal Information')}
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                label={getFieldLabel('First Name')}
                name="firstName"
                value={formData.firstName}
                onChange={handleChange}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                label={getFieldLabel('Last Name')}
                name="lastName"
                value={formData.lastName}
                onChange={handleChange}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                label={getFieldLabel('Age')}
                name="age"
                type="number"
                value={formData.age}
                onChange={handleChange}
                inputProps={{ min: 0, max: 120 }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                select
                label={getFieldLabel('Gender')}
                name="gender"
                value={formData.gender}
                onChange={handleChange}
              >
                <MenuItem value="male">{getFieldLabel( 'Male')}</MenuItem>
                <MenuItem value="female">{getFieldLabel('Female')}</MenuItem>
                <MenuItem value="other">{getFieldLabel('Other')}</MenuItem>
              </TextField>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                label={getFieldLabel('Height (cm)')}
                name="height"
                type="number"
                value={formData.height}
                onChange={handleChange}
                inputProps={{ min: 0 }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                label={getFieldLabel('Weight (kg)')}
                name="weight"
                type="number"
                value={formData.weight}
                onChange={handleChange}
                inputProps={{ min: 0 }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                label={getFieldLabel('Email')}
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                required
                fullWidth
                label={getFieldLabel('Mobile Number')}
                name="mobile"
                value={formData.mobile}
                onChange={handleChange}
              />
            </Grid>

            {/* Language and Voice Preferences Section */}
            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              <Typography variant="h6" gutterBottom>
                {getFieldLabel('Language Preferences')}
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
              <InputLabel>{getFieldLabel('Preferred Language')}</InputLabel>
                <Select
                  name="language"
                  value={formData.languagePreferences.language}
                  onChange={handleLanguageChange}
                  label={getFieldLabel('Preferred Language')}
                >
                  {Object.entries(SUPPORTED_LANGUAGES).map(([code, lang]) => (
                    <MenuItem key={code} value={code}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <span>{lang.native}</span>
                        <Typography variant="caption" color="text.secondary">
                          ({lang.name})
                        </Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                {getFieldLabel('Voice Preferences')}
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.voice_preferences.enabled}
                    onChange={handleChange}
                    name="voice_preferences.enabled"
                  />
                }
                label={getFieldLabel( 'Enable Voice Output')}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                select
                fullWidth
                label={getFieldLabel('Voice Gender')}
                name="voice_preferences.gender"
                value={formData.voice_preferences.gender}
                onChange={handleChange}
                disabled={!formData.voice_preferences.enabled}
              >
                {VOICE_OPTIONS.genders.map(option => (
                  <MenuItem key={option} value={option}>
                  {VOICE_OPTIONS.translations[formData.languagePreferences.language]?.[option] || 
                   VOICE_OPTIONS.translations.en[option]}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                type="number"
                label={getFieldLabel('Voice Speed')}
                name="voice_preferences.speed"
                value={formData.voice_preferences.speed}
                onChange={handleChange}
                disabled={!formData.voice_preferences.enabled}
                inputProps={{ step: 0.1, min: 0.5, max: 2 }}
              />
            </Grid>

            {/* Submit Button */}
            <Grid item xs={12}>
              <Button type="submit" fullWidth variant="contained" color="primary" disabled={loading}>
                {loading ? <CircularProgress size={24} /> : getFieldLabel( 'Submit')}
              </Button>
            </Grid>
          </Grid>
        </form>
      </Paper>
    </Container>
  );
};

export default UserDetailsForm;

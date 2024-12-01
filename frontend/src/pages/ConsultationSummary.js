// src/pages/ConsultationSummary.js
import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  Box,
  Typography,
  Button,
  Grid,
  CircularProgress,
  Alert,
  Divider,
  useTheme,
  IconButton,
  Tooltip,
  Chip,
  FormControl,
  Select,
  MenuItem,
  Collapse
} from '@mui/material';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts';
import DownloadIcon from '@mui/icons-material/Download';
import TranslateIcon from '@mui/icons-material/Translate';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import LocalHospitalIcon from '@mui/icons-material/LocalHospital';
import WarningIcon from '@mui/icons-material/Warning';
import { styled } from '@mui/material/styles';

// Import our components
import AudioControls from '../components/AudioControls';
import TranslationIndicator from '../components/TranslationIndicator';
import FeedbackForm from '../components/FeedbackForm';

// Import utilities
import { consultationApi } from '../utils/api';
import { 
  downloadBlob, 
  getTextDirection, 
  getLanguageName,
  formatDate 
} from '../utils/helpers';
import { SUPPORTED_LANGUAGES } from '../utils/languageMetadata';
import { getTranslation, isRTL } from '../utils/translations';

// Styled Components
const StyledPaper = styled(Paper)(({ theme, dir }) => ({
  padding: theme.spacing(4),
  marginTop: theme.spacing(4),
  marginBottom: theme.spacing(4),
  direction: dir,
}));

const SeverityChip = styled(Chip)(({ theme, severity }) => ({
  backgroundColor: 
    severity <= 3 ? theme.palette.success.light :
    severity <= 7 ? theme.palette.warning.light :
    theme.palette.error.light,
  color: 
    severity <= 3 ? theme.palette.success.dark :
    severity <= 7 ? theme.palette.warning.dark :
    theme.palette.error.dark,
  fontWeight: 'bold',
}));

const InfoSection = styled(Box)(({ theme }) => ({
  marginBottom: theme.spacing(3),
  '& .MuiTypography-root': {
    marginBottom: theme.spacing(1),
  },
}));

const ActionButton = styled(Button)(({ theme }) => ({
  minWidth: 180,
  '& .MuiCircularProgress-root': {
    marginRight: theme.spacing(1),
  },
}));

// Initial state
const initialSummaryState = {
  userDetails: {
    firstName: '',
    lastName: '',
    age: '',
    gender: '',
    height: '',
    weight: '',
    email: '',
    mobile: '',
    preferred_language: 'en'
  },
  diagnosis: {
    symptoms: [],
    description: '',
    severityScore: 0,
    riskLevel: '',
    timeframe: '',
    recommendedDoctor: '',
    confidence: 0
  },
  recommendations: {
    medications: [],
    homeRemedies: [],
    urgency: '',
    safety_concerns: [],
    suggested_improvements: [],
    confidence: 0
  },
  language: {
    source: 'en',
    target: 'en',
    confidence: 0
  },
  translations: {},
  precautions: [],
  created_at: new Date().toISOString(),
  audio: null
};

const ConsultationSummary = () => {
  const { consultationId } = useParams();
  const navigate = useNavigate();
  const theme = useTheme();
  const audioRef = useRef(null);

  // State Management
  const [summary, setSummary] = useState(initialSummaryState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [currentLanguage, setCurrentLanguage] = useState('en');
  const [showAudioControls, setShowAudioControls] = useState(false);
  const [translationLoading, setTranslationLoading] = useState(false);

  // Track component mount state
  const isMounted = useRef(true);

  useEffect(() => {
    // Load user's language preference
    const savedPreferences = JSON.parse(localStorage.getItem('userLanguagePreferences'));
    if (savedPreferences?.preferred) {
      setCurrentLanguage(savedPreferences.preferred);
    }

    return () => {
      isMounted.current = false;
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  // Fetch summary data
  useEffect(() => {
    const fetchSummary = async () => {
      try {
        setLoading(true);
        const data = await consultationApi.getSummary(consultationId);
        
        if (!isMounted.current) return;

        // Transform symptoms data for visualization
        const transformedSymptoms = data.diagnosis?.symptoms?.map(symptom => ({
          ...symptom,
          intensity: parseInt(symptom.severity || symptom.intensity || 0, 10),
          translatedName: symptom.name // Will be updated in translation
        })) || [];

        setSummary(prev => ({
          ...prev,
          ...data,
          diagnosis: {
            ...data.diagnosis,
            symptoms: transformedSymptoms
          }
        }));

        // Handle audio setup if present
        if (data.audio) {
          audioRef.current = new Audio(`data:audio/mp3;base64,${data.audio}`);
        }

        // Fetch translation if needed
        if (currentLanguage !== 'en') {
          await handleTranslation(currentLanguage, data);
        }

      } catch (err) {
        console.error('Error fetching summary:', err);
        if (isMounted.current) {
          setError(getTranslation('fetchError', currentLanguage));
        }
      } finally {
        if (isMounted.current) {
          setLoading(false);
        }
      }
    };

    fetchSummary();
  }, [consultationId]);

  // Handle language change
  const handleLanguageChange = async (newLanguage) => {
    try {
      setTranslationLoading(true);
      setCurrentLanguage(newLanguage);

      // Save preference
      const savedPreferences = JSON.parse(localStorage.getItem('userLanguagePreferences') || '{}');
      localStorage.setItem('userLanguagePreferences', JSON.stringify({
        ...savedPreferences,
        preferred: newLanguage
      }));

      // If English, reset to original content
      if (newLanguage === 'en') {
        setSummary(prev => ({
          ...prev,
          translations: {}
        }));
      } else {
        // Fetch translations
        await handleTranslation(newLanguage, summary);
      }

    } catch (err) {
      console.error('Error changing language:', err);
      setError(getTranslation('translationError', currentLanguage));
    } finally {
      setTranslationLoading(false);
    }
  };

  // Handle translation
  const handleTranslation = async (targetLanguage, content) => {
    try {
      const translatedData = await consultationApi.getTranslatedSummary(
        consultationId,
        targetLanguage
      );

      if (!isMounted.current) return;

      setSummary(prev => ({
        ...prev,
        translations: {
          ...prev.translations,
          [targetLanguage]: translatedData
        }
      }));

    } catch (err) {
      console.error('Translation error:', err);
      throw err;
    }
  };

  // Handle report download
  const handleDownloadReport = async () => {
    try {
      setLoading(true);
      const blob = await consultationApi.getReport(consultationId, currentLanguage);
      downloadBlob(blob, `consultation-report-${consultationId}-${currentLanguage}.pdf`);
    } catch (err) {
      console.error('Error downloading report:', err);
      setError(getTranslation('downloadError', currentLanguage));
    } finally {
      setLoading(false);
    }
  };

  // Get translated content
  const getContent = (key) => {
    if (currentLanguage === 'en') return summary[key];
    return summary.translations[currentLanguage]?.[key] || summary[key];
  };

  // Loading state
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress size={60} thickness={4} />
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Container maxWidth="md">
        <Alert 
          severity="error" 
          sx={{ mt: 4 }}
          action={
            <Button color="inherit" onClick={() => navigate('/')}>
              {getTranslation('returnHome', currentLanguage)}
            </Button>
          }
        >
          {error}
        </Alert>
      </Container>
    );
  }

return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <StyledPaper 
        elevation={3} 
        dir={getTextDirection(currentLanguage)}
      >
        {/* Language Selection & Translation Status */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <Select
              value={currentLanguage}
              onChange={(e) => handleLanguageChange(e.target.value)}
              startAdornment={<TranslateIcon sx={{ mr: 1 }} />}
              disabled={translationLoading}
            >
              {Object.entries(SUPPORTED_LANGUAGES).map(([code, lang]) => (
                <MenuItem key={code} value={code}>
                  {`${lang.native} (${lang.name})`}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          
          {translationLoading && <CircularProgress size={24} />}
        </Box>

        {/* Header Section */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h4" gutterBottom sx={{ color: 'primary.main', fontWeight: 'bold' }}>
            {getTranslation('title', currentLanguage)}
          </Typography>
          
          <Grid container spacing={2} alignItems="center">
            <Grid item>
              <Typography variant="subtitle1" color="text.secondary">
                {getTranslation('consultationId', currentLanguage)}: {consultationId}
              </Typography>
            </Grid>
            <Grid item>
              <Typography variant="subtitle1" color="text.secondary">
                {getTranslation('date', currentLanguage)}: {formatDate(summary.created_at, currentLanguage)}
              </Typography>
            </Grid>
          </Grid>
          
          <Divider sx={{ mt: 2 }} />
        </Box>

        <Grid container spacing={4}>
          {/* Patient Details Section */}
          <Grid item xs={12}>
            <InfoSection>
              <Typography variant="h5" sx={{ color: 'primary.main' }}>
                {getTranslation('patientDetails', currentLanguage)}
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography>
                    <strong>{getTranslation('name', currentLanguage)}:</strong> 
                    {getContent('userDetails').firstName} {getContent('userDetails').lastName}
                  </Typography>
                </Grid>
                {/* Other patient details... */}
              </Grid>
            </InfoSection>
          </Grid>

          {/* Diagnosis Section */}
          <Grid item xs={12}>
            <InfoSection>
              <Typography variant="h5" sx={{ color: 'primary.main' }}>
                {getTranslation('diagnosisTitle', currentLanguage)}
              </Typography>
              
              {getContent('diagnosis').symptoms.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle1">
                    {getTranslation('symptoms', currentLanguage)}:
                  </Typography>
                  {getContent('diagnosis').symptoms.map((symptom, index) => (
                    <Chip
                      key={index}
                      label={symptom.translatedName || symptom.name}
                      sx={{ m: 0.5 }}
                      variant="outlined"
                    />
                  ))}
                </Box>
              )}
              
              {/* Severity and Risk Level */}
              <Box sx={{ mt: 2 }}>
                <SeverityChip
                  severity={getContent('diagnosis').severityScore}
                  label={`${getTranslation('severityScore', currentLanguage)}: ${getContent('diagnosis').severityScore}/10`}
                />
              </Box>
            </InfoSection>
          </Grid>

          {/* Symptoms Chart */}
          {getContent('diagnosis').symptoms.length > 0 && (
            <Grid item xs={12}>
              <InfoSection>
                <Typography variant="h5" sx={{ color: 'primary.main' }}>
                  {getTranslation('symptomsAnalysis', currentLanguage)}
                </Typography>
                <Box sx={{ height: 300, width: '100%' }}>
                  <ResponsiveContainer>
                    <RadarChart data={getContent('diagnosis').symptoms}>
                      <PolarGrid />
                      <PolarAngleAxis 
                        dataKey="translatedName" 
                        tick={{ fill: theme.palette.text.primary }}
                      />
                      <PolarRadiusAxis domain={[0, 10]} />
                      <Radar
                        name={getTranslation('intensity', currentLanguage)}
                        dataKey="intensity"
                        fill={theme.palette.primary.main}
                        fillOpacity={0.6}
                        stroke={theme.palette.primary.main}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </Box>
              </InfoSection>
            </Grid>
          )}

          {/* Recommendations Section */}
          <Grid item xs={12}>
            <InfoSection>
              <Typography variant="h5" sx={{ color: 'primary.main' }}>
                {getTranslation('treatmentTitle', currentLanguage)}
              </Typography>
              
              <Box sx={{ mt: 2 }}>
                <Typography variant="h6">
                  {getTranslation('medications', currentLanguage)}:
                </Typography>
                <ul>
                  {getContent('recommendations').medications?.map((med, index) => (
                    <li key={index}>
                      <Typography>{med}</Typography>
                    </li>
                  ))}
                </ul>

                <Typography variant="h6" sx={{ mt: 2 }}>
                  {getTranslation('homeRemedies', currentLanguage)}:
                </Typography>
                <ul>
                  {getContent('recommendations').homeRemedies?.map((remedy, index) => (
                    <li key={index}>
                      <Typography>{remedy}</Typography>
                    </li>
                  ))}
                </ul>
              </Box>
            </InfoSection>
          </Grid>

          {/* Safety Concerns Section */}
          {getContent('recommendations').safety_concerns?.length > 0 && (
            <Grid item xs={12}>
              <InfoSection>
                <Typography variant="h5" sx={{ color: 'primary.main' }}>
                  {getTranslation('safetyConcerns', currentLanguage)}
                </Typography>
                
                <Alert 
                  severity="warning" 
                  icon={<WarningIcon />}
                  sx={{ mb: 2 }}
                >
                  {getTranslation('safetyWarning', currentLanguage)}
                </Alert>
                
                <ul>
                  {getContent('recommendations').safety_concerns.map((concern, index) => (
                    <li key={index}>
                      <Typography>{concern}</Typography>
                    </li>
                  ))}
                </ul>
              </InfoSection>
            </Grid>
          )}

          {/* Actions Section */}
          <Grid item xs={12}>
            <Box sx={{ 
              display: 'flex', 
              gap: 2, 
              justifyContent: 'center',
              mt: 4,
              mb: 2 
            }}>
              <ActionButton
                variant="contained"
                onClick={handleDownloadReport}
                disabled={loading}
                startIcon={loading ? <CircularProgress size={20} /> : <DownloadIcon />}
              >
                {getTranslation('downloadReport', currentLanguage)}
              </ActionButton>

              <ActionButton
                variant="outlined"
                onClick={() => setShowFeedback(true)}
                color="secondary"
                startIcon={<IconButton size="small"><TranslateIcon /></IconButton>}
              >
                {getTranslation('provideFeedback', currentLanguage)}
              </ActionButton>

              {summary.audio && (
                <ActionButton
                  variant="outlined"
                  onClick={() => setShowAudioControls(!showAudioControls)}
                  startIcon={<VolumeUpIcon />}
                >
                  {getTranslation('toggleAudio', currentLanguage)}
                </ActionButton>
              )}
            </Box>

            {/* Audio Controls */}
            <Collapse in={showAudioControls && summary.audio}>
              <Box sx={{ mt: 2 }}>
                <AudioControls
                  audioUrl={summary.audio}
                  language={currentLanguage}
                  interfaceLanguage={currentLanguage}
                />
              </Box>
            </Collapse>
          </Grid>
        </Grid>

        {/* Disclaimer */}
        <Box sx={{ mt: 4, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
          <Typography 
            variant="body2" 
            color="text.secondary" 
            align="center"
            dir={getTextDirection(currentLanguage)}
          >
            {getTranslation('disclaimer', currentLanguage)}
          </Typography>
        </Box>

        {/* Feedback Dialog */}
        {showFeedback && (
          <FeedbackForm
            consultationId={consultationId}
            onSubmit={() => setShowFeedback(false)}
            onClose={() => setShowFeedback(false)}
            language={currentLanguage}
          />
        )}
      </StyledPaper>
    </Container>
  );
};

export default ConsultationSummary;
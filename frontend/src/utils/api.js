// src/utils/api.js
import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000 // 15 seconds timeout
});


// Add response interceptor for better error handling
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.response?.data || error.message);
    
    let errorMessage = 'An unexpected error occurred';
    
    if (error.response) {
      // Server responded with error
      errorMessage = error.response.data?.detail || error.response.data || errorMessage;
    } else if (error.request) {
      // Request made but no response
      errorMessage = 'No response from server. Please check your connection.';
    }
    
    throw new Error(errorMessage);
  }
);


export const consultationApi = {
  startConsultation: async (userData) => {
    try {
      console.log('Making consultation request with data:', userData);
      
      const response = await api.post('/api/consultation/start', userData);
      console.log('Raw API response:', response);
      
      // Validate the response format
      if (!response.data?.consultation_id || !response.data?.user_details) {
        console.error('Invalid response format:', response.data); // Add this log
        throw new Error('Invalid response format from server');
      }
      
      // Ensure the response has the expected structure
      const consultationData = {
        consultation_id: response.data.consultation_id,
        user_details: response.data.user_details,
        language_preferences: response.data.language_preferences || {
          preferred: userData.language_preferences.preferred,
          interface: userData.language_preferences.interface,
          auto_detect: userData.language_preferences.auto_detect
        },
        created_at: response.data.created_at || new Date().toISOString()
      };
      
      console.log('Formatted consultation data:', consultationData); // Add this log
      return consultationData;
    } catch (error) {
      console.error('Consultation API Error:', error);
      throw error;
    }
  },

  getConsultationStatus: async (consultationId) => {
    try {
      const response = await api.get(`/api/consultation/status/${consultationId}`);
      
      // Validate the response format
      if (!response.data) {
        throw new Error('Invalid consultation data received');
      }

      return response.data;
    } catch (error) {
      console.error('Get consultation status error:', error);
      throw error;
    }
  },

  getSummary: async (consultationId) => {
    const response = await api.get(`/api/diagnostic/summary/${consultationId}`);
    return response.data;
  },

  getReport: async (consultationId, language = 'en') => {
    const response = await api.get(`/api/report/${consultationId}`, {
      params: { language },
      responseType: 'blob'
    });
    return response.data;
  },

  submitFeedback: async (feedbackData) => {
    const response = await api.post('/api/feedback/submit', feedbackData);
    return response.data;
  }
};

export const speechApi = {
  speechToText: async (audioBlob, options = {}) => {
    const formData = new FormData();
    formData.append('audio', audioBlob);
    if (options.sourceLanguage) formData.append('source_language', options.sourceLanguage);
    if (options.enableAutoDetect) formData.append('enable_auto_detect', options.enableAutoDetect);
    
    const response = await api.post('/api/speech/speech-to-text', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  textToSpeech: async (text, options = {}) => {
    const response = await api.post('/api/speech/text-to-speech', {
      text,
      target_language: options.targetLanguage || 'en',
      voice_gender: options.voiceGender || 'female',
      voice_style: options.voiceStyle
    });
    return response.data;
  },

  translateSpeech: async (audioBlob, options = {}) => {
    const formData = new FormData();
    formData.append('audio', audioBlob);
    if (options.sourceLanguage) formData.append('source_language', options.sourceLanguage);
    formData.append('target_language', options.targetLanguage || 'en');
    formData.append('auto_detect', options.autoDetect || true);
    formData.append('voice_gender', options.voiceGender || 'female');

    const response = await api.post('/api/speech/translate-speech', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  }
};

export const WebSocketService = {
  connect: (consultationId, options = {}) => {
    const ws = new WebSocket(`${process.env.REACT_APP_WS_URL || 'ws://localhost:8000'}/ws/${consultationId}`);
    
    // Add language preferences to initial connection
    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'init',
        preferences: {
          language: options.language || 'en',
          autoDetect: options.autoDetect || true,
          voicePreferences: options.voicePreferences || {
            enabled: true,
            gender: 'female'
          }
        }
      }));
      if (options.onOpen) options.onOpen();
    };

    if (options.onMessage) ws.onmessage = options.onMessage;
    if (options.onError) ws.onerror = options.onError;
    if (options.onClose) ws.onclose = options.onClose;

    return ws;
  }
};

export default api;
// src/redux/slices/consultationSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { consultationApi } from '../../utils/api';

export const startConsultation = createAsyncThunk(
  'consultation/start',
  async (userData, { rejectWithValue }) => {
    try {
      const response = await consultationApi.startConsultation(userData);
      console.log('Consultation response:', response);
      return response;
    } catch (error) {
      console.error('Consultation creation error:', error);
      return rejectWithValue(error.message || 'Failed to start consultation');
    }
  }
);

export const getConsultationStatus = createAsyncThunk(
  'consultation/getStatus',
  async (consultationId, { rejectWithValue }) => {
    try {
      const response = await consultationApi.getConsultationStatus(consultationId);
      return response;
    } catch (error) {
      console.error('Get consultation status error:', error);
      return rejectWithValue(error.message || 'Failed to get consultation status');
    }
  }
);

const initialState = {
  consultationId: null,
  userDetails: null,
  chatHistory: [],
  diagnosis: null,
  loading: false,
  error: null,
  status: 'idle',
  languagePreferences: {
    preferred: 'en',
    interface: 'en',
    auto_detect: true
  },
  sessionMetadata: null
};

const consultationSlice = createSlice({
  name: 'consultation',
  initialState,
  reducers: {
    clearConsultation: (state) => {
      return initialState;
    },
    updateLanguagePreferences: (state, action) => {
      state.languagePreferences = action.payload;
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(startConsultation.pending, (state) => {
        state.loading = true;
        state.error = null;
        state.status = 'loading';
      })
      .addCase(startConsultation.fulfilled, (state, action) => {
        state.loading = false;
        state.status = 'succeeded';
        state.consultationId = action.payload.consultation_id;
        state.userDetails = action.payload.user_details;
        state.languagePreferences = action.payload.language_preferences;
        state.sessionMetadata = {
          created_at: action.payload.created_at,
          lastActivity: new Date().toISOString()
        };
      })
      .addCase(startConsultation.rejected, (state, action) => {
        state.loading = false;
        state.status = 'failed';
        state.error = action.payload || 'Failed to start consultation';
      })

      // Get Consultation Status
      .addCase(getConsultationStatus.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(getConsultationStatus.fulfilled, (state, action) => {
        state.loading = false;
        state.status = 'succeeded';
        state.userDetails = action.payload.user_details;
        state.languagePreferences = action.payload.language_preferences;
        state.chatHistory = action.payload.chat_history || [];
        state.diagnosis = action.payload.diagnosis || null;
      })
      .addCase(getConsultationStatus.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload || 'Failed to get consultation status';
      });
  }
});


export const { clearConsultation, updateLanguagePreferences } = consultationSlice.actions;
export default consultationSlice.reducer;
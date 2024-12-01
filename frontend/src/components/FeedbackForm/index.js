// frontend/src/components/FeedbackForm/index.js
import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Rating,
  TextField,
  Button,
  Alert,
  Stack
} from '@mui/material';
import { useDispatch } from 'react-redux';
import axios from 'axios';

const FeedbackForm = ({ consultationId, onSubmit }) => {
  const [feedback, setFeedback] = useState({
    rating: 0,
    symptomAccuracy: 0,
    recommendationHelpfulness: 0,
    comment: ''
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess(false);

    try {
      const response = await axios.post('http://localhost:8000/api/feedback/submit', {
        consultation_id: consultationId,
        rating: feedback.rating,
        symptom_accuracy: feedback.symptomAccuracy,
        recommendation_helpfulness: feedback.recommendationHelpfulness,
        comment: feedback.comment
      });

      setSuccess(true);
      if (onSubmit) onSubmit(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit feedback');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper elevation={3} sx={{ p: 3, maxWidth: 600, mx: 'auto' }}>
      <Typography variant="h6" gutterBottom>
        Your Feedback
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Thank you for your feedback!
        </Alert>
      )}

      <Stack spacing={3}>
        <Box>
          <Typography component="legend">Overall Experience</Typography>
          <Rating
            name="rating"
            value={feedback.rating}
            onChange={(_, value) => setFeedback(prev => ({ ...prev, rating: value }))}
            size="large"
          />
        </Box>

        <Box>
          <Typography component="legend">Symptom Analysis Accuracy</Typography>
          <Rating
            name="symptomAccuracy"
            value={feedback.symptomAccuracy}
            onChange={(_, value) => setFeedback(prev => ({ ...prev, symptomAccuracy: value }))}
          />
        </Box>

        <Box>
          <Typography component="legend">Recommendation Helpfulness</Typography>
          <Rating
            name="recommendationHelpfulness"
            value={feedback.recommendationHelpfulness}
            onChange={(_, value) => setFeedback(prev => ({ ...prev, recommendationHelpfulness: value }))}
          />
        </Box>

        <TextField
          multiline
          rows={4}
          variant="outlined"
          label="Additional Comments"
          value={feedback.comment}
          onChange={(e) => setFeedback(prev => ({ ...prev, comment: e.target.value }))}
          fullWidth
        />

        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={loading || feedback.rating === 0}
          fullWidth
        >
          {loading ? 'Submitting...' : 'Submit Feedback'}
        </Button>
      </Stack>
    </Paper>
  );
};

export default FeedbackForm;
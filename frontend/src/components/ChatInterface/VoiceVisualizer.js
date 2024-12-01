// src/components/ChatInterface/VoiceVisualizer.js
import React, { useEffect, useRef, useState } from 'react';
import { Box, Typography, Fade, Chip } from '@mui/material';
import { styled, keyframes } from '@mui/material/styles';
import { getLanguageName } from '../../utils/helpers';
import { SUPPORTED_LANGUAGES } from '../../utils/languageMetadata';

const Container = styled(Box)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: theme.spacing(1),
}));

const VisualizerContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '3px',
  height: '40px',
  padding: theme.spacing(1),
  width: '100%',
}));

const pulse = keyframes`
  0%, 100% { transform: scaleY(0.3); }
  50% { transform: scaleY(1); }
`;

const Bar = styled(Box)(({ theme, delay, active }) => ({
  width: '3px',
  height: '100%',
  backgroundColor: active ? theme.palette.primary.main : theme.palette.grey[300],
  animation: active ? `${pulse} 1.5s ease-in-out infinite` : 'none',
  animationDelay: `${delay}ms`,
  transformOrigin: '50% 50%',
}));

const StatusText = styled(Typography)(({ theme }) => ({
  fontSize: '0.875rem',
  color: theme.palette.text.secondary,
}));

const TranslationProgress = styled(Box)(({ theme, progress }) => ({
  width: '100%',
  height: '2px',
  backgroundColor: theme.palette.grey[200],
  position: 'relative',
  '&::after': {
    content: '""',
    position: 'absolute',
    left: 0,
    top: 0,
    height: '100%',
    width: `${progress}%`,
    backgroundColor: theme.palette.primary.main,
    transition: 'width 0.3s ease',
  },
}));

const VoiceVisualizer = ({ 
  isRecording,
  detectedLanguage,
  targetLanguage,
  isProcessing,
  processingStage, // 'recording', 'detecting', 'translating', 'processing'
  interfaceLanguage = 'en'
}) => {
  const analyzerRef = useRef(null);
  const animationRef = useRef(null);
  const canvasRef = useRef(null);
  const [volume, setVolume] = useState(0);

  const getStatusText = (stage) => {
    const texts = {
      en: {
        recording: 'Recording...',
        detecting: 'Detecting language...',
        translating: 'Translating...',
        processing: 'Processing...'
      },
      hi: {
        recording: 'रिकॉर्डिंग...',
        detecting: 'भाषा की पहचान...',
        translating: 'अनुवाद...',
        processing: 'प्रसंस्करण...'
      }
      // Add more languages as needed
    };
    return texts[interfaceLanguage]?.[stage] || texts['en'][stage];
  };

  useEffect(() => {
    if (isRecording) {
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
          const audioContext = new (window.AudioContext || window.webkitAudioContext)();
          analyzerRef.current = audioContext.createAnalyser();
          const source = audioContext.createMediaStreamSource(stream);
          source.connect(analyzerRef.current);
          analyzerRef.current.fftSize = 256;
          
          const draw = () => {
            const bufferLength = analyzerRef.current.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            analyzerRef.current.getByteFrequencyData(dataArray);
            
            const average = dataArray.reduce((a, b) => a + b) / bufferLength;
            setVolume(average);
            
            if (canvasRef.current) {
              const canvas = canvasRef.current;
              const ctx = canvas.getContext('2d');
              ctx.clearRect(0, 0, canvas.width, canvas.height);
              
              const barWidth = (canvas.width / bufferLength) * 2.5;
              let x = 0;
              
              for (let i = 0; i < bufferLength; i++) {
                const barHeight = (dataArray[i] / 255) * canvas.height;
                const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
                gradient.addColorStop(0, '#1976d2');
                gradient.addColorStop(1, '#90caf9');
                ctx.fillStyle = gradient;
                ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
                x += barWidth + 1;
              }
            }
            
            animationRef.current = requestAnimationFrame(draw);
          };
          
          draw();
        })
        .catch(err => console.error('Error accessing microphone:', err));
    } else {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      if (canvasRef.current) {
        const ctx = canvasRef.current.getContext('2d');
        ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
      }
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isRecording]);

  if (!isRecording && !isProcessing) {
    return null;
  }

  return (
    <Container>
      {/* Language Detection Chip */}
      {detectedLanguage && (
        <Fade in>
          <Chip
            label={`${getLanguageName(detectedLanguage)} detected`}
            color="primary"
            size="small"
          />
        </Fade>
      )}

      {/* Status Text */}
      <StatusText>
        {getStatusText(processingStage)}
      </StatusText>

      {/* Visualizer */}
      <Box sx={{ width: '100%', height: '40px', position: 'relative' }}>
        <canvas
          ref={canvasRef}
          width={200}
          height={40}
          style={{
            width: '100%',
            height: '100%',
          }}
        />
        <VisualizerContainer>
          {[...Array(5)].map((_, i) => (
            <Bar 
              key={i} 
              delay={i * 100} 
              active={isRecording}
              style={{
                height: isRecording ? `${(volume / 255) * 100}%` : '100%'
              }}
            />
          ))}
        </VisualizerContainer>
      </Box>

      {/* Processing Progress */}
      {isProcessing && (
        <TranslationProgress 
          progress={
            processingStage === 'detecting' ? 33 :
            processingStage === 'translating' ? 66 :
            processingStage === 'processing' ? 100 : 0
          }
        />
      )}
    </Container>
  );
};

export default VoiceVisualizer;
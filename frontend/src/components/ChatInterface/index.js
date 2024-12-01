// src/components/ChatInterface/index.js
import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container,
  Paper,
  Box,
  TextField,
  IconButton,
  Typography,
  CircularProgress,
  Alert,
  Fab,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import MicIcon from '@mui/icons-material/Mic';
import { styled, keyframes } from '@mui/material/styles';
import MessageBubble from './MessageBubble';
import VoiceVisualizer from './VoiceVisualizer';
import LanguageSelector from '../LanguageSelector';
import TranslationIndicator from '../TranslationIndicator';
import { getTranslation } from '../../utils/translations';
import { SUPPORTED_LANGUAGES } from '../../utils/languageMetadata';

// Keyframes for mic animation
const pulse = keyframes`
  0% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(25, 118, 210, 0.4);
  }
  70% {
    transform: scale(1.1);
    box-shadow: 0 0 0 15px rgba(25, 118, 210, 0);
  }
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(25, 118, 210, 0);
  }
`;

const AnimatedMicButton = styled(Fab)(({ theme, isrecording }) => ({
  position: 'absolute',
  bottom: theme.spacing(3),
  right: theme.spacing(3),
  width: 64,
  height: 64,
  animation: isrecording === 'true' ? `${pulse} 1.5s infinite` : 'none',
  backgroundColor: isrecording === 'true' ? theme.palette.error.main : theme.palette.primary.main,
  color: theme.palette.common.white,
  '&:hover': {
    backgroundColor: isrecording === 'true' ? theme.palette.error.dark : theme.palette.primary.dark,
  },
  '& svg': {
    width: 28,
    height: 28,
  },
}));

const ChatContainer = styled(Box)({
  position: 'relative',
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
});

const MessagesContainer = styled(Box)(({ theme }) => ({
  flexGrow: 1,
  overflow: 'auto',
  padding: theme.spacing(2),
  display: 'flex',
  flexDirection: 'column',
  gap: theme.spacing(2),
  '&::-webkit-scrollbar': {
    width: '8px',
  },
  '&::-webkit-scrollbar-track': {
    background: theme.palette.grey[100],
    borderRadius: '4px',
  },
  '&::-webkit-scrollbar-thumb': {
    background: theme.palette.grey[400],
    borderRadius: '4px',
  },
}));

const ChatInterface = () => {
  const { consultationId } = useParams();
  const [inputMessage, setInputMessage] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [wsInstance, setWsInstance] = useState(null);
  const [wsError, setWsError] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const messagesEndRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioPlayerRef = useRef(null);
  const [selectedLanguage, setSelectedLanguage] = useState('en');
  const [autoDetectLanguage, setAutoDetectLanguage] = useState(true);
  const [showOriginalText, setShowOriginalText] = useState(false);
  const [voicePreferences, setVoicePreferences] = useState({
    enabled: true,
    gender: 'female',
    speed: 1
  });
  const [messages, setMessages] = useState([
    {
      type: '', // 'user' or 'bot'
      content: '',
      originalContent: '',
      translatedContent: '',
      language: {
        source: '',
        target: '',
        detected: false,
        confidence: 0
      },
      timestamp: new Date(),
      audio: null,
      analysis: {
        symptoms: [],
        confidence: 0,
        urgency: '',
        requiresEmergency: false,
        recommendations: []
      }
    }
  ]);
  const [settings, setSettings] = useState({
    interfaceLanguage: 'en',
    preferredLanguage: 'en',
    autoDetectLanguage: true,
    voice: {
      enabled: true,
      gender: 'female',
      speed: 1
    }
  });

  const detectSilence = (stream, onSilence, silenceDelay = 3000, minDecibels = -45) => {
    const audioContext = new AudioContext();
    const analyser = audioContext.createAnalyser();
    const microphone = audioContext.createMediaStreamSource(stream);
    const scriptProcessor = audioContext.createScriptProcessor(2048, 1, 1);

    // Add minimum recording duration
    const startTime = Date.now();
    const minRecordingDuration = 2000; // 3 seconds minimum

    analyser.minDecibels = minDecibels;
    

    microphone.connect(analyser);
    analyser.connect(scriptProcessor);
    scriptProcessor.connect(audioContext.destination);

    let lastSound = Date.now();
    scriptProcessor.addEventListener('audioprocess', () => {
      const array = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(array);
      const arraySum = array.reduce((a, value) => a + value, 0);
      const average = arraySum / array.length;

      if (Date.now() - startTime > minRecordingDuration) {
        if (average === 0 && Date.now() - lastSound > silenceDelay) {
          onSilence();
          microphone.disconnect();
          scriptProcessor.disconnect();
          audioContext.close();
       }
     }
    });
  };

  useEffect(() => {
    const savedPreferences = JSON.parse(
      localStorage.getItem('userLanguagePreferences') || '{}'
    );
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
    const wsUrl = `${process.env.REACT_APP_WS_URL || 'ws://localhost:8000'}/ws/${consultationId}`;
    console.log('Connecting to WebSocket:', wsUrl);
   
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket Connected');
      setWsError(null);
    };

    ws.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "error") {
          console.error("Server error:", data.content);
          setWsError(data.content);
          return;
        }
       
        setMessages(prev => [...prev, {
          type: data.type || 'bot',
          content: data.content,
          originalContent: data.original_message,
          translatedContent: data.translated_message,
          language: {
            source: data.language?.source,
            target: data.language?.target,
            detected: data.language?.detected,
            confidence: data.language?.confidence
          },
          timestamp: new Date(data.timestamp || Date.now()),
          audio: data.audio,
          analysis: {
            symptoms: data.symptoms || [],
            confidence: data.confidence_scores?.overall,
            urgency: data.urgency,
            requiresEmergency: data.requires_emergency,
            recommendations: data.recommendations
          }
        }]);
   
        if (data.audio && voicePreferences.enabled) {
          const audio = new Audio(`data:audio/mp3;base64,${data.audio}`);
          audio.playbackRate = voicePreferences.speed;
          audioPlayerRef.current = audio;
          try {
            await audio.play();
          } catch (error) {
            console.error('Error playing audio:', error);
          }
        }
      } catch (error) {
        console.error('Error processing message:', error);
        setWsError('Error processing message');
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setWsError('Connection error occurred');
    };

    ws.onclose = () => {
      console.log('WebSocket Disconnected');
      setWsError('Connection closed. Please refresh the page.');
    };

    setWsInstance(ws);

    return () => {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      if (ws) {
        ws.close();
      }
    };
  }, [consultationId, voicePreferences.enabled, voicePreferences.speed, setMessages, setWsError, setWsInstance]);


  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      audioChunksRef.current = [];
  
      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
  
      mediaRecorderRef.current.onstop = async () => {
        try {
          setIsProcessing(true);
          
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append('audio', audioBlob, 'recording.webm');
          formData.append('consultation_id', consultationId); // Add this line
          formData.append('source_language', selectedLanguage);
          formData.append('enable_auto_detect', String(autoDetectLanguage));
          formData.append('voice_preferences', JSON.stringify(voicePreferences));
  
          const response = await fetch(
            `${process.env.REACT_APP_API_URL}/api/speech/speech-to-text`,
            {
              method: 'POST',
              body: formData,
            }
          );
  
          if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
          }
  
          const data = await response.json();
          
          if (data.text) {
            handleSendMessage(data.text);
            // Update language if auto-detected
            if (data.language?.detected && autoDetectLanguage) {
              setSelectedLanguage(data.language.code);
            }
          }
        } catch (error) {
          console.error('Speech to text error:', error);
          setWsError('Failed to process voice input: ' + error.message);
        } finally {
          setIsProcessing(false);
        }
      };
  
      mediaRecorderRef.current.start();
      setIsRecording(true);
  
      detectSilence(stream, () => {
        if (mediaRecorderRef.current?.state === 'recording') {
          stopRecording();
        }
      });
  
    } catch (error) {
      console.error('Error accessing microphone:', error);
      setWsError('Failed to access microphone: ' + error.message);
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleWsMessage = async (data) => {
    const messageData = {
      type: data.type || 'bot',
      content: data.content,
      originalContent: data.original_content,
      translatedContent: data.translated_content,
      language: {
        source: data.language?.source || settings.preferredLanguage,
        target: data.language?.target || settings.preferredLanguage,
        detected: data.language?.detected || false,
        confidence: data.language?.confidence || 1
      },
      timestamp: new Date(data.timestamp || Date.now()),
      audio: data.audio,
      analysis: {
        symptoms: data.symptoms || [],
        confidence: data.confidence_scores?.overall || 1,
        urgency: data.urgency,
        requiresEmergency: data.requires_emergency,
        recommendations: data.recommendations || []
      }
    };
  
    setMessages(prev => [...prev, messageData]);
  };
  
  const handleSendMessage = (text = inputMessage) => {
    if (!text.trim() || !wsInstance) return;
  
    const message = {
      type: 'message',
      content: text.trim(),
      language: {
        source: selectedLanguage,
        autoDetect: autoDetectLanguage
      },
      preferences: {
        voice: voicePreferences,
        showOriginalText: showOriginalText
      }
    };
  
    try {
      setMessages(prev => [...prev, {
        type: 'user',
        content: text.trim(),
        language: {
          source: selectedLanguage,
          target: selectedLanguage,
          detected: false,
          confidence: 1
        },
        timestamp: new Date(),
        analysis: null
      }]);
  
      wsInstance.send(JSON.stringify(message));
      setInputMessage('');
    } catch (error) {
      console.error('Error sending message:', error);
      setWsError('Failed to send message: ' + error.message);
    }
  };

  const handleLanguageChange = (language) => {
    setSettings(prev => {
      const newSettings = {
        ...prev,
        preferredLanguage: language
      };
      localStorage.setItem('userLanguagePreferences', JSON.stringify(newSettings));
      return newSettings;
    });
  };
  
  const handleAutoDetectChange = (value) => {
    setSettings(prev => {
      const newSettings = {
        ...prev,
        autoDetectLanguage: value
      };
      localStorage.setItem('userLanguagePreferences', JSON.stringify(newSettings));
      return newSettings;
    });
  };

  return (
    <Container maxWidth="md">
      <Paper elevation={3} sx={{ height: 'calc(100vh - 100px)', p: 2 }}>
        <ChatContainer>

          {/* Language Settings */}
          <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between' }}>
            <LanguageSelector
              selectedLanguage={settings.preferredLanguage}
              interfaceLanguage={settings.interfaceLanguage}
              onLanguageChange={(lang) => handleLanguageChange(lang)}
              autoDetect={settings.autoDetectLanguage}
              onAutoDetectChange={(value) => handleAutoDetectChange(value)}
            />
          </Box>

          {wsError && (
            <Alert severity="error" onClose={() => setWsError(null)} sx={{ mb: 2 }}>
              {wsError}
            </Alert>
          )}

          <MessagesContainer>
            {messages.map((message, index) => (
              <MessageBubble 
                key={index} 
                message={message}
                isUser={message.type === 'user'}
              />
            ))}
            <div ref={messagesEndRef} />
          </MessagesContainer>

          <Box sx={{ display: 'flex', gap: 1, mb: isRecording ? 8 : 0 }}>
            <TextField
              fullWidth
              variant="outlined"
              placeholder="Type your message..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              disabled={isRecording || isProcessing}
            />

            <IconButton
              color="primary"
              onClick={() => handleSendMessage()}
              disabled={!inputMessage.trim() || isProcessing}
            >
              {isProcessing ? <CircularProgress size={24} /> : <SendIcon />}
            </IconButton>
          </Box>

          {isRecording && (
            <Box sx={{ position: 'absolute', bottom: 80, left: 0, right: 0, px: 2 }}>
              <VoiceVisualizer />
            </Box>
          )}

          <AnimatedMicButton
            isrecording={isRecording.toString()}
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isProcessing}
            color={isRecording ? "error" : "primary"}
          >
            <MicIcon />
          </AnimatedMicButton>
        </ChatContainer>
      </Paper>
    </Container>
  );
};

export default ChatInterface;
// src/components/AudioControls/index.js
import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  IconButton,
  Slider,
  Typography,
  Menu,
  MenuItem,
  FormControl,
  Select,
  Tooltip,
  Paper
} from '@mui/material';
import { styled } from '@mui/material/styles';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import SettingsIcon from '@mui/icons-material/Settings';
import { VOICE_OPTIONS } from '../../utils/languageMetadata';
import { formatAudioDuration } from '../../utils/helpers';

const ControlsWrapper = styled(Paper)(({ theme }) => ({
    padding: theme.spacing(1),
    display: 'flex',
    alignItems: 'center',
    gap: theme.spacing(1),
    backgroundColor: theme.palette.grey[50],
  }));
  
  const TimeDisplay = styled(Typography)(({ theme }) => ({
    minWidth: 70,
    fontSize: '0.875rem',
    color: theme.palette.text.secondary,
  }));
  
  const AudioControls = ({
    audioUrl,
    language,
    voiceGender = 'female',
    onVoiceChange,
    interfaceLanguage = 'en'
  }) => {
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [playbackSpeed, setPlaybackSpeed] = useState(1);
    const [volume, setVolume] = useState(1);
    const [settingsAnchorEl, setSettingsAnchorEl] = useState(null);
    
    const audioRef = useRef(new Audio(audioUrl));
    const animationRef = useRef();

    const getGenderLabel = (gender) => {
      return VOICE_OPTIONS.translations[interfaceLanguage]?.[gender] || 
             VOICE_OPTIONS.translations['en'][gender];
    };
  
    useEffect(() => {
      const audio = audioRef.current;
      audio.playbackRate = playbackSpeed;
      audio.volume = volume;
  
      const handleLoadedMetadata = () => {
        setDuration(audio.duration);
      };
  
      const handleEnded = () => {
        setIsPlaying(false);
        setCurrentTime(0);
        cancelAnimationFrame(animationRef.current);
      };
  
      audio.addEventListener('loadedmetadata', handleLoadedMetadata);
      audio.addEventListener('ended', handleEnded);
  
      return () => {
        audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
        audio.removeEventListener('ended', handleEnded);
        audio.pause();
        cancelAnimationFrame(animationRef.current);
      };
    }, [audioUrl, playbackSpeed, volume]);
  
    const handlePlayPause = () => {
      if (isPlaying) {
        audioRef.current.pause();
        cancelAnimationFrame(animationRef.current);
      } else {
        audioRef.current.play();
        animationRef.current = requestAnimationFrame(updateProgress);
      }
      setIsPlaying(!isPlaying);
    };
  
    const updateProgress = () => {
      setCurrentTime(audioRef.current.currentTime);
      animationRef.current = requestAnimationFrame(updateProgress);
    };
  
    const handleTimeChange = (_, value) => {
      setCurrentTime(value);
      audioRef.current.currentTime = value;
    };
  
    const handleVolumeChange = (_, value) => {
      setVolume(value);
      audioRef.current.volume = value;
    };
  
    const handleSpeedChange = (speed) => {
      setPlaybackSpeed(speed);
      audioRef.current.playbackRate = speed;
    };
  
    const handleVoiceGenderChange = (event) => {
      if (onVoiceChange) {
        onVoiceChange(event.target.value);
      }
    };
  
    const getLabel = (key) => {
      const labels = {
        en: {
          speed: 'Speed',
          volume: 'Volume',
          voice: 'Voice',
          settings: 'Settings'
        },
        hi: {
          speed: 'गति',
          volume: 'आवाज़',
          voice: 'आवाज',
          settings: 'सेटिंग्स'
        }
        // Add more languages as needed
      };
      return labels[interfaceLanguage]?.[key] || labels.en[key];
    };
  
    return (
      <ControlsWrapper elevation={0}>
        {/* Play/Pause Button */}
        <IconButton onClick={handlePlayPause} size="small">
          {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
        </IconButton>
  
        {/* Time Display */}
        <TimeDisplay>
          {formatAudioDuration(currentTime)} / {formatAudioDuration(duration)}
        </TimeDisplay>
  
        {/* Progress Slider */}
        <Slider
          size="small"
          value={currentTime}
          max={duration}
          onChange={handleTimeChange}
          sx={{ mx: 2, flexGrow: 1 }}
        />
  
        {/* Volume Control */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 100 }}>
          <VolumeUpIcon fontSize="small" />
          <Slider
            size="small"
            value={volume}
            min={0}
            max={1}
            step={0.1}
            onChange={handleVolumeChange}
          />
        </Box>
  
        {/* Voice Settings */}
        <FormControl size="small" sx={{ minWidth: 100 }}>
          <Select
            value={voiceGender}
            onChange={handleVoiceGenderChange}
            displayEmpty
          >
            {VOICE_OPTIONS.genders.map(gender => (
              <MenuItem key={gender} value={gender}>
                {getGenderLabel(gender)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
  
        {/* Settings Button */}
        <Tooltip title={getLabel('settings')}>
          <IconButton
            size="small"
            onClick={(e) => setSettingsAnchorEl(e.currentTarget)}
          >
            <SettingsIcon fontSize="small" />
          </IconButton>
        </Tooltip>
  
        {/* Settings Menu */}
        <Menu
          anchorEl={settingsAnchorEl}
          open={Boolean(settingsAnchorEl)}
          onClose={() => setSettingsAnchorEl(null)}
        >
          <MenuItem disabled>
            <Typography variant="caption">{getLabel('speed')}</Typography>
          </MenuItem>
          {[0.5, 0.75, 1, 1.25, 1.5, 2].map(speed => (
            <MenuItem
              key={speed}
              selected={playbackSpeed === speed}
              onClick={() => {
                handleSpeedChange(speed);
                setSettingsAnchorEl(null);
              }}
            >
              {speed}x
            </MenuItem>
          ))}
        </Menu>
      </ControlsWrapper>
    );
  };
  
  export default AudioControls;
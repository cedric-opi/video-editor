import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Upload, Video, Download, Play, Eye, Trash2, Clock, CheckCircle, AlertCircle, Crown, Mail } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import './App.css';

import PremiumPlans from './components/PremiumPlans';
import PaymentSuccess from './components/PaymentSuccess';
import PaymentCancel from './components/PaymentCancel';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ViralVideoAnalyzer = () => {
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [segments, setSegments] = useState([]);
  const [processingStatus, setProcessingStatus] = useState({});
  const [uploading, setUploading] = useState(false);
  const [showPremiumModal, setShowPremiumModal] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [premiumStatus, setPremiumStatus] = useState({ is_premium: false, max_video_duration: 300 });

  // Load videos on component mount and check for upgrade parameter
  useEffect(() => {
    loadVideos();
    
    // Check for upgrade parameter in URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('upgrade') === 'true') {
      setShowPremiumModal(true);
    }
  }, []);

  // Poll processing status for active videos
  useEffect(() => {
    const interval = setInterval(() => {
      videos.forEach(video => {
        if (['processing', 'analyzing', 'segmenting', 'generating', 'finalizing'].includes(video.processing_status)) {
          checkProcessingStatus(video.id);
        }
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [videos]);

  const loadVideos = async () => {
    try {
      const response = await axios.get(`${API}/video-list`);
      setVideos(response.data.videos);
    } catch (error) {
      console.error('Error loading videos:', error);
    }
  };

  const checkPremiumStatus = async (email) => {
    if (!email) return;
    
    try {
      const response = await axios.post(`${API}/premium-status`, {
        user_email: email
      });
      setPremiumStatus(response.data);
    } catch (error) {
      console.error('Error checking premium status:', error);
    }
  };

  const handleEmailChange = (email) => {
    setUserEmail(email);
    if (email) {
      checkPremiumStatus(email);
    }
  };

  const checkProcessingStatus = async (videoId) => {
    try {
      const response = await axios.get(`${API}/processing-status/${videoId}`);
      setProcessingStatus(prev => ({
        ...prev,
        [videoId]: response.data
      }));

      // Update video status in list
      setVideos(prev => prev.map(video => 
        video.id === videoId 
          ? { ...video, processing_status: response.data.status }
          : video
      ));
    } catch (error) {
      console.error('Error checking status:', error);
    }
  };

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file || !file.type.startsWith('video/')) {
      alert('Please select a valid video file');
      return;
    }

    if (file.size > 500 * 1024 * 1024) { // 500MB limit
      alert('File too large. Maximum size is 500MB');
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (userEmail) {
        formData.append('user_email', userEmail);
      }

      const response = await axios.post(`${API}/upload-video`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      // Add new video to list
      const newVideo = {
        id: response.data.video_id,
        original_filename: file.name,
        duration: response.data.duration,
        file_size: file.size,
        processing_status: 'processing',
        created_at: new Date().toISOString()
      };

      setVideos(prev => [newVideo, ...prev]);
      
      // Start polling for this video
      checkProcessingStatus(response.data.video_id);

    } catch (error) {
      console.error('Upload error:', error);
      alert(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    },
    multiple: false
  });

  const selectVideo = async (video) => {
    setSelectedVideo(video);
    
    if (video.processing_status === 'completed') {
      try {
        // Load analysis
        const analysisResponse = await axios.get(`${API}/video-analysis/${video.id}`);
        setAnalysis(analysisResponse.data);

        // Load segments
        const segmentsResponse = await axios.get(`${API}/video-segments/${video.id}`);
        setSegments(segmentsResponse.data.segments);
      } catch (error) {
        console.error('Error loading video data:', error);
      }
    } else {
      setAnalysis(null);
      setSegments([]);
    }
  };

  const downloadSegment = async (videoId, segmentNumber) => {
    try {
      const response = await axios.get(`${API}/download-segment/${videoId}/${segmentNumber}`, {
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `viral_segment_${segmentNumber}.mp4`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Download error:', error);
      alert('Download failed');
    }
  };

  const deleteVideo = async (videoId) => {
    if (!window.confirm('Are you sure you want to delete this video?')) return;

    try {
      await axios.delete(`${API}/video/${videoId}`);
      setVideos(prev => prev.filter(video => video.id !== videoId));
      if (selectedVideo && selectedVideo.id === videoId) {
        setSelectedVideo(null);
        setAnalysis(null);
        setSegments([]);
      }
    } catch (error) {
      console.error('Delete error:', error);
      alert('Delete failed');
    }
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatFileSize = (bytes) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'processing':
      case 'analyzing':
      case 'segmenting':
      case 'generating':
      case 'finalizing': return 'text-blue-600';
      case 'error': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircle className="w-5 h-5" />;
      case 'processing':
      case 'analyzing':
      case 'segmenting':
      case 'generating':
      case 'finalizing': return <Clock className="w-5 h-5" />;
      case 'error': return <AlertCircle className="w-5 h-5" />;
      default: return <Video className="w-5 h-5" />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-6 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-white mb-4 tracking-tight">
            Viral Video <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400">Analyzer</span>
          </h1>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto">
            AI-powered analysis system that breaks viral videos into shareable highlights with captions and voice-overs
          </p>
          
          {/* Premium Status and Email Input */}
          <div className="max-w-md mx-auto mt-8 space-y-4">
            <div className="flex items-center gap-3">
              <Mail className="w-5 h-5 text-gray-400" />
              <input
                type="email"
                placeholder="Enter your email (optional)"
                value={userEmail}
                onChange={(e) => handleEmailChange(e.target.value)}
                className="flex-1 bg-gray-800/50 border border-gray-600 rounded-lg px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-purple-500"
                data-testid="user-email-input"
              />
            </div>
            
            {premiumStatus.is_premium ? (
              <div className="flex items-center justify-center gap-2 text-yellow-400">
                <Crown className="w-5 h-5" />
                <span className="font-medium">Premium Active • {premiumStatus.max_video_duration/60} min videos</span>
              </div>
            ) : (
              <div className="flex items-center justify-center gap-3">
                <span className="text-gray-400">Free Plan • 5 min videos</span>
                <button
                  onClick={() => setShowPremiumModal(true)}
                  className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white px-4 py-1 rounded-full text-sm font-medium transition-all duration-200 flex items-center gap-1"
                  data-testid="upgrade-premium-btn"
                >
                  <Crown className="w-4 h-4" />
                  Upgrade to Premium
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Upload Section */}
        <div className="max-w-4xl mx-auto mb-12">
          <div 
            {...getRootProps()} 
            className={`border-3 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-300 ${
              isDragActive 
                ? 'border-purple-400 bg-purple-500/10' 
                : 'border-gray-600 hover:border-purple-500 bg-gray-800/50'
            }`}
            data-testid="video-upload-zone"
          >
            <input {...getInputProps()} />
            <Upload className="w-16 h-16 mx-auto text-purple-400 mb-4" />
            <h3 className="text-2xl font-semibold text-white mb-2">
              {uploading ? 'Uploading...' : 'Upload Your Video'}
            </h3>
            <p className="text-gray-400 mb-4">
              Drag and drop your video here, or click to select
            </p>
            <p className="text-sm text-gray-500">
              Supports MP4, AVI, MOV, MKV, WebM • Max {premiumStatus.max_video_duration/60} minutes • Up to 500MB
              {!premiumStatus.is_premium && (
                <span className="text-purple-400 ml-2">
                  (Upgrade to Premium for 30-minute videos)
                </span>
              )}
            </p>
            {uploading && (
              <div className="mt-4">
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div className="bg-purple-500 h-2 rounded-full animate-pulse w-1/2"></div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Video List */}
          <div className="lg:col-span-1">
            <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-6 shadow-2xl">
              <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
                <Video className="w-6 h-6" />
                Your Videos
              </h2>
              
              {videos.length === 0 ? (
                <p className="text-gray-400 text-center py-8">No videos uploaded yet</p>
              ) : (
                <div className="space-y-4 max-h-96 overflow-y-auto">
                  {videos.map((video) => (
                    <div 
                      key={video.id}
                      className={`p-4 rounded-xl cursor-pointer transition-all duration-200 ${
                        selectedVideo?.id === video.id 
                          ? 'bg-purple-600/20 border-2 border-purple-500' 
                          : 'bg-gray-700/50 hover:bg-gray-700 border-2 border-transparent'
                      }`}
                      onClick={() => selectVideo(video)}
                      data-testid={`video-item-${video.id}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <h3 className="text-white font-medium truncate">{video.original_filename}</h3>
                          <div className="flex items-center gap-4 mt-1 text-sm text-gray-400">
                            <span>{formatDuration(video.duration)}</span>
                            <span>{formatFileSize(video.file_size)}</span>
                          </div>
                          <div className={`flex items-center gap-2 mt-2 text-sm ${getStatusColor(video.processing_status)}`}>
                            {getStatusIcon(video.processing_status)}
                            <span className="capitalize">{video.processing_status}</span>
                          </div>
                          {processingStatus[video.id] && processingStatus[video.id].progress > 0 && (
                            <div className="mt-2">
                              <div className="w-full bg-gray-600 rounded-full h-1.5">
                                <div 
                                  className="bg-purple-500 h-1.5 rounded-full transition-all duration-500"
                                  style={{ width: `${processingStatus[video.id].progress}%` }}
                                ></div>
                              </div>
                              <p className="text-xs text-gray-400 mt-1">{processingStatus[video.id].message}</p>
                            </div>
                          )}
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteVideo(video.id);
                          }}
                          className="text-red-400 hover:text-red-300 transition-colors"
                          data-testid={`delete-video-${video.id}`}
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Analysis & Segments */}
          <div className="lg:col-span-2">
            {selectedVideo ? (
              <div className="space-y-8">
                {/* Analysis Results */}
                {analysis && (
                  <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-6 shadow-2xl" data-testid="analysis-results">
                    <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
                      <Eye className="w-6 h-6" />
                      Viral Analysis
                    </h2>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                      <div>
                        <h3 className="text-lg font-semibold text-purple-400 mb-3">Viral Techniques</h3>
                        <div className="flex flex-wrap gap-2">
                          {analysis.viral_techniques.map((technique, index) => (
                            <span key={index} className="px-3 py-1 bg-purple-600/20 text-purple-300 rounded-full text-sm">
                              {technique}
                            </span>
                          ))}
                        </div>
                      </div>
                      
                      <div>
                        <h3 className="text-lg font-semibold text-blue-400 mb-3">Engagement Factors</h3>
                        <div className="flex flex-wrap gap-2">
                          {analysis.engagement_factors.map((factor, index) => (
                            <span key={index} className="px-3 py-1 bg-blue-600/20 text-blue-300 rounded-full text-sm">
                              {factor}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                    
                    <div>
                      <h3 className="text-lg font-semibold text-green-400 mb-3">Content Summary</h3>
                      <p className="text-gray-300 leading-relaxed">{analysis.content_summary}</p>
                    </div>
                    
                    <div className="mt-6">
                      <h3 className="text-lg font-semibold text-yellow-400 mb-3">Detailed Analysis</h3>
                      <p className="text-gray-300 leading-relaxed">{analysis.analysis_text}</p>
                    </div>
                  </div>
                )}

                {/* Video Segments */}
                {segments.length > 0 && (
                  <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-6 shadow-2xl" data-testid="video-segments">
                    <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
                      <Play className="w-6 h-6" />
                      Viral Highlights ({segments.length} clips)
                    </h2>
                    
                    <div className="grid grid-cols-1 gap-4">
                      {segments.map((segment) => (
                        <div key={segment.id} className="bg-gray-700/50 rounded-xl p-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                              <div className="flex items-center gap-4 mb-2">
                                <span className="text-sm font-medium text-purple-400">
                                  Segment {segment.segment_number}
                                </span>
                                <span className="text-sm text-gray-400">
                                  {formatDuration(segment.start_time)} - {formatDuration(segment.end_time)}
                                </span>
                                <span className="text-sm text-gray-400">
                                  ({formatDuration(segment.duration)})
                                </span>
                                <div className="flex items-center">
                                  <span className="text-sm text-yellow-400">★ {(segment.highlight_score * 100).toFixed(0)}%</span>
                                </div>
                              </div>
                              
                              <h4 className="text-white font-medium mb-2">{segment.caption_text}</h4>
                              <p className="text-gray-300 text-sm mb-3">{segment.audio_script}</p>
                            </div>
                            
                            <button
                              onClick={() => downloadSegment(selectedVideo.id, segment.segment_number)}
                              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
                              data-testid={`download-segment-${segment.segment_number}`}
                            >
                              <Download className="w-4 h-4" />
                              Download
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Processing Status */}
                {selectedVideo.processing_status !== 'completed' && (
                  <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-6 shadow-2xl">
                    <h2 className="text-2xl font-bold text-white mb-6">Processing Status</h2>
                    <div className="text-center">
                      {processingStatus[selectedVideo.id] ? (
                        <div>
                          <div className="w-full bg-gray-700 rounded-full h-3 mb-4">
                            <div 
                              className="bg-gradient-to-r from-purple-500 to-pink-500 h-3 rounded-full transition-all duration-500"
                              style={{ width: `${processingStatus[selectedVideo.id].progress}%` }}
                            ></div>
                          </div>
                          <p className="text-lg text-white mb-2">{processingStatus[selectedVideo.id].message}</p>
                          <p className="text-sm text-gray-400">{processingStatus[selectedVideo.id].progress}% complete</p>
                        </div>
                      ) : (
                        <div className="animate-pulse">
                          <div className="w-full bg-gray-700 rounded-full h-3 mb-4"></div>
                          <p className="text-gray-400">Loading status...</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-12 shadow-2xl text-center">
                <Video className="w-16 h-16 mx-auto text-gray-600 mb-4" />
                <h2 className="text-2xl font-bold text-white mb-2">Select a Video</h2>
                <p className="text-gray-400">Choose a video from the list to view analysis and download segments</p>
              </div>
            )}
          </div>
        </div>

        {/* Features Section */}
        <div className="max-w-6xl mx-auto mt-16">
          <h2 className="text-3xl font-bold text-white text-center mb-12">How It Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-purple-600/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Upload className="w-8 h-8 text-purple-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">Upload Video</h3>
              <p className="text-gray-400">Upload your viral video (up to 5 minutes)</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-600/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Eye className="w-8 h-8 text-blue-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">AI Analysis</h3>
              <p className="text-gray-400">AI analyzes viral techniques and engagement factors</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-green-600/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Download className="w-8 h-8 text-green-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">Download Clips</h3>
              <p className="text-gray-400">Get highlight clips with captions and voice-overs</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ViralVideoAnalyzer;
import React, { useState, useEffect, useRef } from 'react';
import { Send, MessageSquarePlus, MessageSquare, Paperclip, Loader2, Phone, PhoneOff, Mic, MicOff, Globe, Bot, Sparkles, Server, Database, Cpu, Code, Mail, Headphones, Settings } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { AudioQueue } from './utils/audioQueue';
import { CaptchaGate } from './components/CaptchaGate';


const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

function App() {
  const navigate = useNavigate();
  const [conversationId, setConversationId] = useState('');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [agentLanguage, setAgentLanguage] = useState('Bengali');
  const [isFlying, setIsFlying] = useState(false);

  // CAPTCHA state
  const [isVerified, setIsVerified] = useState(() => {
    const solvedAt = localStorage.getItem('captchaSolvedAt');
    if (!solvedAt) return false;

    const ONE_DAY = 24 * 60 * 60 * 1000;
    const isStillValid = (Date.now() - parseInt(solvedAt, 10)) < ONE_DAY;

    if (!isStillValid) {
      localStorage.removeItem('captchaSolvedAt');
    }

    return isStillValid;
  });

  // Voice call states
  const [isCallActive, setIsCallActive] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isVoiceThinking, setIsVoiceThinking] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Live voice refs
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const processorRef = useRef(null);
  const audioQueueRef = useRef(null);
  const isAgentSpeakingRef = useRef(false);
  const speakingTimeoutRef = useRef(null);
  const isInitialGreetingRef = useRef(true);

  const setAgentSpeaking = (isSpeaking) => {
    if (!isInitialGreetingRef.current) return; // Only apply hard-mute during the initial greeting

    if (isSpeaking) {
      if (speakingTimeoutRef.current) {
        clearTimeout(speakingTimeoutRef.current);
        speakingTimeoutRef.current = null;
      }
      isAgentSpeakingRef.current = true;
    } else {
      speakingTimeoutRef.current = setTimeout(() => {
        isAgentSpeakingRef.current = false;
        isInitialGreetingRef.current = false; // After first greeting ends, allow barge-in forever
      }, 1000); // 1000ms hang time to clear hardware latency and acoustic tail
    }
  };

  // Ringing effect refs
  const ringIntervalRef = useRef(null);
  const hasAIPickedUpRef = useRef(false);

  useEffect(() => {
    setConversationId(generateUUID());

    // Fetch initial language setting
    fetch('/api/admin/settings')
      .then(res => res.json())
      .then(data => {
        if (data && data.agent_language) {
          setAgentLanguage(data.agent_language);
        }
      })
      .catch(err => console.error("Failed to fetch language setting", err));

    return () => {
      endCall();
    };
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleNewChat = () => {
    if (isCallActive) endCall();
    setConversationId(generateUUID());
    setMessages([]);
    setInput('');
  };

  const handleLanguageChange = async (e) => {
    const newLang = e.target.value;
    setAgentLanguage(newLang);
    try {
      await fetch('/api/admin/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'agent_language', value: newLang })
      });
    } catch (err) {
      console.error("Failed to update language", err);
    }
  };

  // ----------------------------------------------------
  // Text Chat Logic
  // ----------------------------------------------------
  const handleQuickSend = async (text) => {
    if (isLoading) return;
    const userMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetch(`/api/chat/${conversationId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) throw new Error('Network response was not ok');
      const data = await response.json();
      setMessages((prev) => [...prev, { role: 'assistant', content: data.assistant_response }]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${error.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    setIsFlying(true);
    setTimeout(() => setIsFlying(false), 600);

    const userMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    const messageText = input;
    setInput('');
    setIsLoading(true);

    if (isCallActive) {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        // Route text through the live voice websocket
        try {
          wsRef.current.send(JSON.stringify({ text: messageText }));
          setIsVoiceThinking(true);
        } catch (error) {
          console.error('Error sending message via WS:', error);
          setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${error.message}` }]);
        } finally {
          setIsLoading(false);
        }
      } else {
        console.error('Voice call active but websocket is closed.');
        setMessages((prev) => [...prev, { role: 'assistant', content: 'Error: Voice connection lost. Message not sent.' }]);
        setIsLoading(false);
      }
      return;
    }

    try {
      const response = await fetch(`/api/chat/${conversationId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText }),
      });

      if (!response.ok) throw new Error('Network response was not ok');
      const data = await response.json();
      setMessages((prev) => [...prev, { role: 'assistant', content: data.assistant_response }]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${error.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/upload', { method: 'POST', body: formData });
      if (!response.ok) throw new Error('Upload failed');
      const data = await response.json();

      const fileMessage = `Here is my document: ${data.url}`;
      setMessages((prev) => [...prev, { role: 'user', content: fileMessage }]);
      setIsLoading(true);

      if (isCallActive) {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          try {
            wsRef.current.send(JSON.stringify({ text: fileMessage }));
            setIsVoiceThinking(true);
          } catch (error) {
            console.error('Error sending file via WS:', error);
            setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${error.message}` }]);
          } finally {
            setIsLoading(false);
            setIsUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
          }
        } else {
          console.error('Voice call active but websocket is closed.');
          setMessages((prev) => [...prev, { role: 'assistant', content: 'Error: Voice connection lost. File uploaded but message not sent.' }]);
          setIsLoading(false);
          setIsUploading(false);
          if (fileInputRef.current) fileInputRef.current.value = '';
        }
        return;
      }

      const chatResponse = await fetch(`/api/chat/${conversationId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: fileMessage }),
      });
      if (!chatResponse.ok) throw new Error('Chat failed');
      const chatData = await chatResponse.json();
      setMessages((prev) => [...prev, { role: 'assistant', content: chatData.assistant_response }]);
    } catch (error) {
      console.error('Error uploading file:', error);
      setMessages((prev) => [...prev, { role: 'assistant', content: `Upload error: ${error.message}` }]);
    } finally {
      setIsUploading(false);
      setIsLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // ----------------------------------------------------
  // Voice Live Call Logic
  // ----------------------------------------------------
  const toggleCall = () => {
    if (isCallActive || isConnecting) {
      endCall();
    } else {
      startCall();
    }
  };

  const startRinging = (ctx) => {
    try {
      const playRing = () => {
        if (!ctx || ctx.state === 'closed') return;
        const osc1 = ctx.createOscillator();
        const osc2 = ctx.createOscillator();
        const gainNode = ctx.createGain();

        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(440, ctx.currentTime);
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(480, ctx.currentTime);

        gainNode.gain.setValueAtTime(0, ctx.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.1, ctx.currentTime + 0.05);
        gainNode.gain.setValueAtTime(0.1, ctx.currentTime + 1.0);
        gainNode.gain.linearRampToValueAtTime(0, ctx.currentTime + 1.1);

        osc1.connect(gainNode);
        osc2.connect(gainNode);
        gainNode.connect(ctx.destination);

        osc1.start(ctx.currentTime);
        osc2.start(ctx.currentTime);
        osc1.stop(ctx.currentTime + 1.2);
        osc2.stop(ctx.currentTime + 1.2);
      };

      playRing();
      ringIntervalRef.current = setInterval(playRing, 3000);
    } catch (e) {
      console.warn('Could not play ringing sound', e);
    }
  };

  const stopRinging = () => {
    if (ringIntervalRef.current) {
      clearInterval(ringIntervalRef.current);
      ringIntervalRef.current = null;
    }
  };

  const startCall = async () => {
    setIsConnecting(true);
    hasAIPickedUpRef.current = false;
    try {
      // 1. Get Microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      mediaStreamRef.current = stream;

      // Create a SINGLE unified AudioContext for the entire session (16kHz)
      // This prevents Windows/Chrome from constantly switching hardware sample rates,
      // which causes severe pitch shifting ("chipmunk" or "Darth Vader" effects).
      const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      startRinging(audioContext);

      // 2. Initialize Audio Queue (for playback) using the unified context
      const audioQueue = new AudioQueue(audioContext, {
        onPlaybackStart: () => { setAgentSpeaking(true); },
        onPlaybackEnd: () => { setAgentSpeaking(false); },
      });
      await audioQueue.init();
      audioQueueRef.current = audioQueue;

      // 3. Connect WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/voice/ws/${conversationId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsCallActive(true);
        isInitialGreetingRef.current = true; // Reset for new calls
        console.log("Voice WS connected, waiting for AI to answer...");
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (!hasAIPickedUpRef.current && (data.audioB64 || data.text || data.chat_message)) {
          hasAIPickedUpRef.current = true;
          stopRinging();
          setIsConnecting(false);
        }

        if (data.audioB64 || data.text || data.chat_message) {
          setIsVoiceThinking(false);
        }

        if (data.interrupted) {
          audioQueue.stop(); // Stop current playback on barge-in
        }
        if (data.turnComplete) {
          audioQueue.flush(); // Instantly play whatever is in the buffer if the turn finishes early
        }
        if (data.audioB64) {
          setAgentSpeaking(true); // Pre-emptively mute while buffering
          audioQueue.addAudioFromBase64(data.audioB64);
        }
        if (data.chat_message) {
          setMessages(prev => [...prev, { role: 'assistant', content: data.chat_message }]);
        }
        if (data.text) {
          setMessages(prev => {
            const last = prev[prev.length - 1];
            // If the last message is assistant, append to it (streaming text)
            // Or just add new message
            if (last && last.role === 'assistant') {
              const updated = [...prev];
              updated[updated.length - 1] = { ...last, content: last.content + ' ' + data.text };
              return updated;
            } else {
              return [...prev, { role: 'assistant', content: data.text }];
            }
          });
        }
      };

      ws.onclose = (event) => {
        console.log("Voice WS closed", event.code, event.reason);
        if (!hasAIPickedUpRef.current) {
          alert("Call failed: Could not connect to the voice server. Please check your network or server configuration.");
        }
        endCall();
      };

      ws.onerror = (error) => {
        console.error("Voice WS error:", error);
      };

      // 4. Record and send audio
      const source = audioContext.createMediaStreamSource(stream);

      // ScriptProcessor is deprecated but works everywhere. AudioWorklet is better for production.
      const processor = audioContext.createScriptProcessor(1024, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

        // Mute microphone upload during ringing. 
        // This prevents Gemini from hearing the ringing sound, which causes it to hallucinate or prematurely abort its greeting.
        if (!hasAIPickedUpRef.current) return;

        if (isAgentSpeakingRef.current) return; // Don't send mic audio while agent is speaking

        const inputData = e.inputBuffer.getChannelData(0);
        // Convert Float32 to Int16 PCM
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          let s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Convert Int16Array to base64
        const buffer = new Uint8Array(pcm16.buffer);
        let binary = '';
        for (let i = 0; i < buffer.byteLength; i++) {
          binary += String.fromCharCode(buffer[i]);
        }
        const base64Str = window.btoa(binary);

        wsRef.current.send(JSON.stringify({ audioB64: base64Str }));
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

    } catch (err) {
      console.error("Failed to start call", err);
      alert("Microphone access denied or error starting call.");
      endCall();
    }
  };

  const endCall = () => {
    stopRinging();
    setIsConnecting(false);
    setIsCallActive(false);
    setIsVoiceThinking(false);

    if (speakingTimeoutRef.current) {
      clearTimeout(speakingTimeoutRef.current);
      speakingTimeoutRef.current = null;
    }
    isAgentSpeakingRef.current = false;

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop());
      mediaStreamRef.current = null;
    }
    if (audioQueueRef.current) {
      audioQueueRef.current.stop();
      audioQueueRef.current = null;
    }
  };

  const actionButtons = (
    <div className="action-buttons">
      <div className="language-selector" style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--surface-light)', padding: '6px 12px', borderRadius: '20px', border: '1px solid var(--border)', fontSize: '0.9rem' }}>
        <Globe size={16} color="var(--primary-light)" />
        <select
          value={agentLanguage}
          onChange={handleLanguageChange}
          style={{ background: 'transparent', border: 'none', color: 'var(--text-main)', outline: 'none', cursor: 'pointer' }}
        >
          <option value="Bengali">Bengali</option>
          <option value="English">English</option>
          <option value="Spanish">Spanish</option>
          <option value="Portuguese">Portuguese</option>
        </select>
      </div>
      <motion.button
        className={`new-chat-btn ${isCallActive ? 'active-voice-btn' : ''}`}
        onClick={toggleCall}
        style={{ backgroundColor: isCallActive ? '#ef4444' : (isConnecting ? '#f59e0b' : ''), position: 'relative', overflow: 'hidden' }}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        {isConnecting && <div className="ripple-container"></div>}
        <span style={{ position: 'relative', zIndex: 1, display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isCallActive ? <PhoneOff size={18} /> : (isConnecting ? <Loader2 className="spin" size={18} /> : <Phone size={18} />)}
          <span className="btn-text">{isCallActive ? 'End Live Call' : (isConnecting ? 'Connecting...' : 'Call AI')}</span>
        </span>
      </motion.button>
      <motion.button
        className="new-chat-btn"
        onClick={handleNewChat}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <MessageSquarePlus size={18} />
        <span className="btn-text">New Chat</span>
      </motion.button>
    </div>
  );

  if (!isVerified) {
    return <CaptchaGate onSolved={() => {
      setIsVerified(true);
      localStorage.setItem('captchaSolvedAt', Date.now().toString());
    }} />;
  }

  return (
    <div className="app-container">
      <div className="ambient-aurora">
        <div className="aurora-blob primary"></div>
        <div className="aurora-blob secondary"></div>
      </div>

      <header className="header">
        <div className="header-brand">
          <img src="/logo.png" alt="Unified Cloud Logo" className="brand-logo" />
        </div>
        {actionButtons}
      </header>

      <main className="chat-container">
        {messages.length === 0 ? (
          <motion.div
            className="empty-state"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <img src="/logo.png" alt="Unified Cloud Logo" className="empty-state-logo" />
            <h2>Welcome to Unified Cloud</h2>
            <p>Discover seamless cloud hosting, powerful servers, and smart AI tools tailored for your success.</p>

            <div className="suggestion-cards">
              <motion.div
                className="suggestion-card blue"
                onClick={() => handleQuickSend("Tell me about Domain Service & Management.")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.1 }}
              >
                <div className="card-header">
                  <Globe className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">Domain Service</h3>
                <p className="card-desc">Register, renew, and secure your online identity with our domain services.</p>
              </motion.div>

              <motion.div
                className="suggestion-card orange"
                onClick={() => handleQuickSend("What cloud hosting and infrastructure solutions do you provide?")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.15 }}
              >
                <div className="card-header">
                  <Server className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">Cloud Service</h3>
                <p className="card-desc">Reliable, scalable, and secure cloud infrastructure with 99.9% uptime.</p>
              </motion.div>

              <motion.div
                className="suggestion-card purple"
                onClick={() => handleQuickSend("How can Business Email Solutions enhance our communication?")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
              >
                <div className="card-header">
                  <Mail className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">Business Email</h3>
                <p className="card-desc">Professional, secure email services tailored for startups to enterprises.</p>
              </motion.div>

              <motion.div
                className="suggestion-card teal"
                onClick={() => handleQuickSend("Tell me more about Bulk SMS and OTP services.")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.25 }}
              >
                <div className="card-header">
                  <MessageSquare className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">Bulk SMS & OTP</h3>
                <p className="card-desc">Fast and reliable messaging for promotions and secure OTP verification.</p>
              </motion.div>

              <motion.div
                className="suggestion-card rose"
                onClick={() => handleQuickSend("What Call Center Solutions do you offer?")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.3 }}
              >
                <div className="card-header">
                  <Headphones className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">Call Center Solution</h3>
                <p className="card-desc">BTRC-licensed platform for seamless sales, CRM, and customer support.</p>
              </motion.div>

              <motion.div
                className="suggestion-card indigo"
                onClick={() => handleQuickSend("How can Agentic AI and Automation help my business?")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.35 }}
              >
                <div className="card-header">
                  <Bot className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">Agentic AI</h3>
                <p className="card-desc">Smart AI agents that automate customer support, workflows, and operations.</p>
              </motion.div>

              <motion.div
                className="suggestion-card green"
                onClick={() => handleQuickSend("Tell me about your Business Automation Solutions.")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.4 }}
              >
                <div className="card-header">
                  <Settings className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">Business Automation</h3>
                <p className="card-desc">Intelligent systems to simplify operations and manage workflows smoothly.</p>
              </motion.div>
            </div>
          </motion.div>
        ) : (
          messages.map((msg, index) => (
            <motion.div
              key={index}
              className={`message-wrapper ${msg.role}`}
              initial={{ opacity: 0, y: 15, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ type: "spring", stiffness: 260, damping: 20 }}
            >
              <div className={`avatar ${msg.role}`}>
                {msg.role === 'user' ? 'U' : <Bot size={20} />}
              </div>
              <div className="message-bubble">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
            </motion.div>
          ))
        )}

        {isLoading && (
          <motion.div
            className="message-wrapper assistant"
            initial={{ opacity: 0, y: 15, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 20 }}
          >
            <div className="avatar assistant"><Bot size={20} /></div>
            <div className="message-bubble typing-indicator">
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
            </div>
          </motion.div>
        )}
        <div ref={messagesEndRef} />
      </main>

      <div className="input-container" style={isCallActive ? { flexDirection: 'column', alignItems: 'center' } : {}}>
        {isCallActive && (
          <div className="voice-controls" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: isInputFocused ? '4px' : '10px' }}>
            <motion.div
              className={`mic-button recording ${isVoiceThinking ? 'thinking' : ''}`}
              style={{
                width: isInputFocused ? '48px' : '80px',
                height: isInputFocused ? '48px' : '80px',
                borderRadius: '50%',
                background: isVoiceThinking ? 'linear-gradient(135deg, #10b981, #3b82f6)' : 'var(--brand-gradient)',
                color: 'white', display: 'flex', justifyContent: 'center', alignItems: 'center',
                boxShadow: isVoiceThinking ? '0 0 35px rgba(16, 185, 129, 0.6)' : '0 0 25px rgba(102, 45, 145, 0.4)',
                marginBottom: isInputFocused ? '4px' : '10px',
                transition: 'width 0.3s ease, height 0.3s ease, margin-bottom 0.3s ease'
              }}
              animate={isVoiceThinking ? { scale: [1, 1.05, 1], rotate: [0, 5, -5, 0] } : { scale: [1, 1.15, 1] }}
              transition={isVoiceThinking ? { repeat: Infinity, duration: 1 } : { repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
            >
              {isVoiceThinking ? <Loader2 size={isInputFocused ? 20 : 32} className="spin" /> : <Mic size={isInputFocused ? 20 : 32} />}
            </motion.div>
            {!isInputFocused && (
              <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '10px' }}>
                Live call active. Speak naturally or write a message.
              </p>
            )}
          </div>
        )}

        <form className="input-form" onSubmit={handleSend} style={{ width: '100%' }}>
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handleFileUpload}
            accept="image/*,.pdf,.doc,.docx"
          />
          <motion.button
            type="button"
            className="attachment-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || isUploading}
            title="Upload Document"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {isUploading ? <Loader2 size={20} className="spin" /> : <Paperclip size={20} />}
          </motion.button>

          <input
            type="text"
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onFocus={() => setIsInputFocused(true)}
            onBlur={() => setIsInputFocused(false)}
            placeholder={isCallActive ? "Write a message during the call..." : "Write a message here..."}
            disabled={isLoading || isUploading}
          />
          <motion.button
            type="submit"
            className={`send-btn ${isFlying ? 'flying' : ''}`}
            disabled={!input.trim() || isLoading || isUploading}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Send size={18} />
          </motion.button>
        </form>
      </div>
    </div>
  );
}

export default App;

import React, { useState, useEffect, useRef } from 'react';
import { Send, MessageSquarePlus, MessageSquare, Paperclip, Loader2, Phone, PhoneOff, Mic, MicOff, Globe, Bot, Sparkles, Server, Database, Cpu, Code } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import { AudioQueue } from './utils/audioQueue';
import { CaptchaGate } from './components/CaptchaGate';


const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

function App() {
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
  
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  
  // Live voice refs
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const processorRef = useRef(null);
  const audioQueueRef = useRef(null);
  
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
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`/api/chat/${conversationId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage.content }),
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
      const audioQueue = new AudioQueue(audioContext);
      await audioQueue.init();
      audioQueueRef.current = audioQueue;

      // 3. Connect WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/voice/ws/${conversationId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsCallActive(true);
        console.log("Voice WS connected, waiting for AI to answer...");
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (!hasAIPickedUpRef.current && (data.audioB64 || data.text || data.chat_message)) {
          hasAIPickedUpRef.current = true;
          stopRinging();
          setIsConnecting(false);
        }

        if (data.interrupted) {
          audioQueue.stop(); // Stop current playback on barge-in
        }
        if (data.turnComplete) {
          audioQueue.flush(); // Instantly play whatever is in the buffer if the turn finishes early
        }
        if (data.audioB64) {
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
    <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', alignItems: 'center' }}>
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
          {isCallActive ? 'End Live Call' : (isConnecting ? 'Connecting...' : 'Call AI')}
        </span>
      </motion.button>
      <motion.button 
        className="new-chat-btn" 
        onClick={handleNewChat}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <MessageSquarePlus size={18} />
        New Chat
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
          <img src="/logo.png" alt="Unified IT Logo" className="brand-logo" />
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
            <img src="/logo.png" alt="Unified IT Logo" className="empty-state-logo" />
            <h2>Welcome to Unified IT</h2>
            <p>How can I help you with your IT services today?</p>
            
            <div className="suggestion-cards">
              <motion.div 
                className="suggestion-card blue" 
                onClick={() => handleQuickSend("Tell me more about Web Hosting options.")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.1 }}
              >
                <div className="card-header">
                  <Server className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">Web Hosting</h3>
                <p className="card-desc">Reliable and fast web hosting solutions for your business.</p>
              </motion.div>

              <motion.div 
                className="suggestion-card orange" 
                onClick={() => handleQuickSend("What cloud server solutions do you provide?")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
              >
                <div className="card-header">
                  <Database className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">Cloud Servers</h3>
                <p className="card-desc">Scalable VPS and dedicated cloud servers for high performance.</p>
              </motion.div>

              <motion.div 
                className="suggestion-card purple" 
                onClick={() => handleQuickSend("How can you help with custom AI development?")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.3 }}
              >
                <div className="card-header">
                  <Cpu className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">AI Development</h3>
                <p className="card-desc">Custom AI, SaaS, and PaaS solutions tailored to your needs.</p>
              </motion.div>

              <motion.div 
                className="suggestion-card teal" 
                onClick={() => handleQuickSend("Tell me about your API integrations.")}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.4 }}
              >
                <div className="card-header">
                  <Code className="card-icon" size={24} />
                  <Sparkles className="sparkle-icon" size={18} />
                </div>
                <h3 className="card-title">API Integrations</h3>
                <p className="card-desc">Seamless API solutions to connect your enterprise tools.</p>
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

      <div className="input-container">
        {isCallActive ? (
          <div className="voice-controls" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '20px' }}>
            <motion.div 
              className="mic-button recording"
              style={{
                width: '80px', height: '80px', borderRadius: '50%',
                background: 'var(--brand-gradient)',
                color: 'white', display: 'flex', justifyContent: 'center', alignItems: 'center',
                boxShadow: '0 0 25px rgba(102, 45, 145, 0.4)',
              }}
              animate={{ scale: [1, 1.15, 1] }}
              transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
            >
              <Mic size={32} />
            </motion.div>
            <p style={{ marginTop: '16px', color: '#94a3b8', fontSize: '0.9rem' }}>
              Live call active. Speak naturally.
            </p>
          </div>
        ) : (
          <form className="input-form" onSubmit={handleSend}>
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
              placeholder="Write a message here..."
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
        )}
      </div>
    </div>
  );
}

export default App;

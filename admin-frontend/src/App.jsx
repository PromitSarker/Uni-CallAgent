import React, { useState, useEffect } from 'react';
import { LayoutDashboard, Users, FileText, Send, Database, AlertCircle, CheckCircle, DollarSign, Settings, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// Do not hard-code localhost: it points at the administrator's own computer
// when this panel is opened from another device.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8001/api`;

async function getApiError(response) {
  const body = await response.json().catch(() => null);
  return body?.detail || body?.message || `Request failed (${response.status})`;
}

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <div className="app-container">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      <main className="main-content">
        {activeTab === 'dashboard' && <DashboardView />}
        {activeTab === 'leads' && <LeadsView />}
        {activeTab === 'knowledge' && <KnowledgeBaseView />}
        {activeTab === 'billing' && <BillingView />}
        {activeTab === 'settings' && <SettingsView />}
      </main>
    </div>
  );
}

function Sidebar({ activeTab, setActiveTab }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={20} /> },
    { id: 'leads', label: 'Collected Leads', icon: <Users size={20} /> },
    { id: 'knowledge', label: 'Knowledge Base', icon: <Database size={20} /> },
    { id: 'billing', label: 'Billing / Cost', icon: <DollarSign size={20} /> },
    { id: 'settings', label: 'Settings', icon: <Settings size={20} /> },
  ];

  return (
    <div className="sidebar">
      <div className="brand">
        <div className="brand-icon">
          <Database size={28} />
        </div>
        <span className="brand-text">RT Admin</span>
      </div>
      <div className="nav-menu">
        {navItems.map((item) => (
          <div
            key={item.id}
            className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
            onClick={() => setActiveTab(item.id)}
          >
            {item.icon}
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardView() {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSummary, setSelectedSummary] = useState(null);

  const fetchConversations = () => {
    setLoading(true);
    fetch(`${API_BASE_URL}/admin/conversations`)
      .then(res => res.json())
      .then(data => {
        setConversations(data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch conversations", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchConversations();
  }, []);

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this conversation?")) return;
    try {
      const res = await fetch(`${API_BASE_URL}/admin/conversations/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await getApiError(res));
      fetchConversations();
    } catch (err) {
      console.error(err);
      alert(`Could not delete conversation: ${err.message}`);
    }
  };

  const handleDeleteAll = async () => {
    if (!window.confirm("Are you sure you want to delete ALL conversations? This cannot be undone.")) return;
    try {
      const res = await fetch(`${API_BASE_URL}/admin/conversations`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await getApiError(res));
      fetchConversations();
    } catch (err) {
      console.error(err);
      alert(`Could not delete all conversations: ${err.message}`);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Overview of chat interactions and state</p>
      </div>

      <div className="dashboard-grid">
        <div className="glass-card">
          <h3 style={{ color: 'var(--text-muted)', marginBottom: '8px', fontSize: '0.9rem' }}>Total Conversations</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 'bold' }}>{conversations.length}</div>
        </div>
        <div className="glass-card">
          <h3 style={{ color: 'var(--text-muted)', marginBottom: '8px', fontSize: '0.9rem' }}>Escalated to Human</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--danger)' }}>
            {conversations.filter(c => c.escalated).length}
          </div>
        </div>
      </div>

      <div className="glass-card table-container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>Recent Conversations</h3>
          <button 
            className="btn" 
            style={{ background: 'var(--danger)', color: 'white', padding: '6px 12px', fontSize: '0.85rem' }} 
            onClick={handleDeleteAll}
          >
            Delete All
          </button>
        </div>
        {loading ? (
          <p style={{ marginTop: '20px', color: 'var(--text-muted)' }}>Loading...</p>
        ) : (
          <table style={{ marginTop: '20px' }}>
            <thead>
              <tr>
                <th>ID</th>
                <th>Messages</th>
                <th>Last Intent</th>
                <th>Status</th>
                <th>Summary</th>
                <th>Last Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {conversations.map((conv, idx) => (
                <tr key={idx}>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                    {conv.conversation_id.substring(0, 13)}...
                  </td>
                  <td>{conv.message_count}</td>
                  <td>
                    {conv.last_intent ? (
                      <span className="badge intent">{conv.last_intent}</span>
                    ) : '-'}
                  </td>
                  <td>
                    {conv.escalated ? (
                      <span className="badge escalated">Escalated</span>
                    ) : (
                      <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.2)', color: 'var(--success)' }}>Active</span>
                    )}
                  </td>
                  <td style={{ maxWidth: '300px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, marginRight: '8px' }}>
                        {conv.session_summary || 'No summary'}
                      </span>
                      {conv.session_summary && (
                        <button 
                          className="btn" 
                          style={{ padding: '4px 10px', fontSize: '0.75rem', flexShrink: 0 }}
                          onClick={() => setSelectedSummary(conv.session_summary)}
                        >
                          View
                        </button>
                      )}
                    </div>
                  </td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {new Date(conv.last_updated).toLocaleString()}
                  </td>
                  <td>
                    <button 
                      className="btn" 
                      style={{ background: 'transparent', border: '1px solid var(--danger)', color: 'var(--danger)', padding: '4px 10px', fontSize: '0.75rem' }}
                      onClick={() => handleDelete(conv.conversation_id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {conversations.length === 0 && (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No conversations found.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      <AnimatePresence>
        {selectedSummary && (
          <motion.div 
            className="modal-overlay" 
            onClick={() => setSelectedSummary(null)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div 
              className="modal-content glass-card" 
              onClick={e => e.stopPropagation()} 
              style={{ maxWidth: '600px', width: '90%', maxHeight: '80vh', overflowY: 'auto' }}
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              transition={{ type: "spring", bounce: 0.4, duration: 0.5 }}
            >
              <button className="modal-close" onClick={() => setSelectedSummary(null)}>
                <X size={20} />
              </button>
              <h3 className="modal-title">Conversation Summary</h3>
              <div 
                className="summary-content"
                dangerouslySetInnerHTML={{ __html: selectedSummary.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }}
              />
              <div style={{ marginTop: '24px', textAlign: 'right' }}>
                <button className="btn btn-outline" onClick={() => setSelectedSummary(null)}>Close</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function LeadsView() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE_URL}/admin/collected_data`)
      .then(res => res.json())
      .then(data => {
        setLeads(data);
        setLoading(false);
      });
  }, []);

  const getPivotedData = () => {
    const sessionMap = {};
    const exactColumns = [
      'Type',
      'Name',
      'Designation',
      'Company Name & Address',
      'Mobile',
      'Email',
      'Trade License',
      'NID',
      'Passport Size Photo',
      'Masking Name',
      'Temporary Password'
    ];
    
    leads.forEach(lead => {
      if (!sessionMap[lead.session_id]) {
        sessionMap[lead.session_id] = { session_id: lead.session_id, last_collected: lead.created_at };
      }
      sessionMap[lead.session_id][lead.key] = lead.value;
      if (new Date(lead.created_at) > new Date(sessionMap[lead.session_id].last_collected)) {
        sessionMap[lead.session_id].last_collected = lead.created_at;
      }
    });

    const rows = Object.values(sessionMap).sort((a, b) => new Date(b.last_collected) - new Date(a.last_collected));
    
    return { columns: exactColumns, rows };
  };

  const { columns, rows } = getPivotedData();

  const renderCell = (value) => {
    if (!value) return <span style={{color: 'var(--text-muted)'}}>-</span>;
    if (value.startsWith('http')) {
      return <a href={value} target="_blank" rel="noopener noreferrer" style={{color: 'var(--primary-light)', textDecoration: 'underline'}}>View Document</a>;
    }
    return value;
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Collected Leads</h1>
        <p className="page-subtitle">Data gathered during lead generation flows</p>
      </div>

      <div className="glass-card table-container">
        {loading ? (
          <p style={{ color: 'var(--text-muted)' }}>Loading...</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Session ID</th>
                {columns.map(col => (
                  <th key={col}>{col}</th>
                ))}
                <th>Last Collected</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={idx}>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{row.session_id.substring(0, 13)}...</td>
                  {columns.map(col => (
                    <td key={col}>{renderCell(row[col])}</td>
                  ))}
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {new Date(row.last_collected).toLocaleString()}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={columns.length + 2} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No collected leads found.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function KnowledgeBaseView() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [docText, setDocText] = useState('');
  const [docMetadata, setDocMetadata] = useState('');
  const [pdfFile, setPdfFile] = useState(null);
  const [pushing, setPushing] = useState(false);
  const [message, setMessage] = useState(null);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/documents`);
      if (!res.ok) throw new Error(await getApiError(res));
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch (err) {
      console.error('Failed to fetch documents', err);
      setMessage({ type: 'error', text: `Could not load documents: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handlePush = async (e) => {
    e.preventDefault();
    if (!docText.trim() && !pdfFile) return;
    
    setPushing(true);
    setMessage(null);
    
    try {
      if (pdfFile) {
        // Handle PDF upload
        const formData = new FormData();
        formData.append('file', pdfFile);
        if (docMetadata.trim()) {
          formData.append('metadata_str', docMetadata);
        }

        const res = await fetch(`${API_BASE_URL}/documents/upload`, {
          method: 'POST',
          body: formData
        });

        if (!res.ok) throw new Error(await getApiError(res));
      } else {
        // Handle plain text
        let meta = {};
        if (docMetadata.trim()) {
          meta = JSON.parse(docMetadata);
        }
        
        const res = await fetch(`${API_BASE_URL}/documents`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: docText, metadata: meta })
        });
        
        if (!res.ok) throw new Error(await getApiError(res));
      }
      
      setMessage({ type: 'success', text: 'Document successfully pushed to ChromaDB!' });
      setDocText('');
      setDocMetadata('');
      setPdfFile(null);
      // Reset file input element
      const fileInput = document.getElementById('pdf-upload');
      if (fileInput) fileInput.value = '';
      fetchDocs();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Error parsing metadata or pushing.' });
    } finally {
      setPushing(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this document?")) return;
    try {
      const res = await fetch(`${API_BASE_URL}/documents/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await getApiError(res));
      fetchDocs();
    } catch (err) {
      console.error(err);
      setMessage({ type: 'error', text: `Could not delete document: ${err.message}` });
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Knowledge Base</h1>
        <p className="page-subtitle">Manage documents for RAG (Retrieval-Augmented Generation)</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
        <div className="glass-card" style={{ height: 'fit-content' }}>
          <h3 style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={20} color="var(--primary-light)" />
            Add New Document
          </h3>
          
          <form onSubmit={handlePush}>
            <div className="input-group">
              <label>Upload PDF Document (Optional)</label>
              <input 
                id="pdf-upload"
                type="file" 
                accept=".pdf"
                onChange={(e) => setPdfFile(e.target.files[0])}
                style={{ marginBottom: '12px', fontSize: '0.9rem' }}
              />
            </div>

            <div className="input-group">
              <label>Or Enter Document Content Manually</label>
              <textarea 
                className="input-field" 
                rows="6" 
                placeholder="Enter FAQ or knowledge base information..."
                value={docText}
                onChange={(e) => setDocText(e.target.value)}
                required={!pdfFile}
                disabled={!!pdfFile}
                style={{ resize: 'vertical' }}
              />
            </div>
            
            <div className="input-group">
              <label>Metadata (JSON optional)</label>
              <textarea 
                className="input-field" 
                rows="2" 
                placeholder='{"category": "pricing", "source": "manual"}'
                value={docMetadata}
                onChange={(e) => setDocMetadata(e.target.value)}
                style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
              />
            </div>
            
            {message && (
              <div style={{ 
                padding: '12px', 
                borderRadius: '8px',
                marginBottom: '20px',
                background: message.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                color: message.type === 'success' ? 'var(--success)' : 'var(--danger)',
                display: 'flex', alignItems: 'center', gap: '8px'
              }}>
                {message.type === 'success' ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
                {message.text}
              </div>
            )}
            
            <button type="submit" className="btn" style={{ width: '100%' }} disabled={pushing || (!docText.trim() && !pdfFile)}>
              <Send size={18} />
              {pushing ? 'Pushing to DB...' : 'Push Document'}
            </button>
          </form>
        </div>

        <div className="glass-card">
          <h3 style={{ marginBottom: '24px' }}>Vector Store Documents</h3>
          {loading ? (
             <p style={{ color: 'var(--text-muted)' }}>Loading documents...</p>
          ) : documents.length === 0 ? (
             <p style={{ color: 'var(--text-muted)' }}>No documents in ChromaDB.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {documents.map((doc, idx) => (
                <div key={idx} className="doc-item">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div className="doc-id">ID: {doc.id}</div>
                    <button 
                      onClick={() => handleDelete(doc.id)}
                      style={{ 
                        background: 'transparent', border: 'none', color: 'var(--danger)', 
                        cursor: 'pointer', padding: '4px', borderRadius: '4px',
                        transition: 'background 0.2s'
                      }}
                      onMouseOver={e => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)'}
                      onMouseOut={e => e.currentTarget.style.background = 'transparent'}
                    >
                      Delete
                    </button>
                  </div>
                  <div className="doc-content">{doc.text}</div>
                  {doc.metadata && Object.keys(doc.metadata).length > 0 && (
                    <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px dashed var(--glass-border)', fontSize: '0.8rem', color: 'var(--primary-light)', fontFamily: 'monospace' }}>
                      {JSON.stringify(doc.metadata)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function BillingView() {
  const [costData, setCostData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchCost = () => {
    setLoading(true);
    fetch(`${API_BASE_URL}/admin/cost_summary`)
      .then(res => res.json())
      .then(data => {
        setCostData(data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch cost summary", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchCost();
  }, []);

  const handleReset = async () => {
    if (!window.confirm("Are you sure you want to reset all token usage logs? This will delete all cost history.")) return;
    try {
      const res = await fetch(`${API_BASE_URL}/admin/cost_summary`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await getApiError(res));
      fetchCost();
    } catch (err) {
      console.error(err);
      alert(`Could not reset cost summary: ${err.message}`);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Billing & Cost</h1>
        <p className="page-subtitle">Track exact token usage and API costs</p>
      </div>

      <div className="dashboard-grid">
        <div className="glass-card">
          <h3 style={{ color: 'var(--text-muted)', marginBottom: '8px', fontSize: '0.9rem' }}>Total Input Tokens</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 'bold' }}>
            {loading ? '...' : (costData?.total_input_tokens || 0).toLocaleString()}
          </div>
        </div>
        <div className="glass-card">
          <h3 style={{ color: 'var(--text-muted)', marginBottom: '8px', fontSize: '0.9rem' }}>Total Output Tokens</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 'bold' }}>
            {loading ? '...' : (costData?.total_output_tokens || 0).toLocaleString()}
          </div>
        </div>
        <div className="glass-card">
          <h3 style={{ color: 'var(--text-muted)', marginBottom: '8px', fontSize: '0.9rem' }}>Total Usage Duration (s)</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 'bold' }}>
            {loading ? '...' : (costData?.total_duration_seconds || 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s
          </div>
        </div>
        <div className="glass-card">
          <h3 style={{ color: 'var(--text-muted)', marginBottom: '8px', fontSize: '0.9rem' }}>Cost Per Minute</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--success)' }}>
            ${loading ? '...' : (costData?.cost_per_minute_usd || 0).toFixed(6)}
          </div>
        </div>
      </div>

      <div className="glass-card" style={{ marginTop: '24px' }}>
        <h3 style={{ color: 'var(--text-muted)', marginBottom: '8px', fontSize: '0.9rem' }}>Estimated Total Cost</h3>
        <div style={{ fontSize: '3rem', fontWeight: 'bold', color: 'var(--success)', marginBottom: '24px' }}>
          ${loading ? '...' : (costData?.total_cost_usd || 0).toFixed(6)}
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            className="btn" 
            style={{ background: 'var(--danger)', color: 'white' }} 
            onClick={handleReset}
          >
            Reset Cost Tracking
          </button>
          <button className="btn" onClick={fetchCost} style={{ background: 'var(--primary)', color: 'white' }}>
            Refresh
          </button>
        </div>
      </div>
    </div>
  );
}

function SettingsView() {
  const [language, setLanguage] = useState('Bengali');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/admin/settings`)
      .then(res => res.json())
      .then(data => {
        if (data && data.agent_language) {
          setLanguage(data.agent_language);
        }
      })
      .catch(err => console.error("Failed to fetch settings", err));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE_URL}/admin/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'agent_language', value: language })
      });
      if (!res.ok) throw new Error(await getApiError(res));
      setMessage({ type: 'success', text: 'Language updated successfully!' });
    } catch (err) {
      console.error(err);
      setMessage({ type: 'error', text: `Failed to update language: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Configure global agent behavior</p>
      </div>

      <div className="glass-card" style={{ maxWidth: '600px' }}>
        <h3 style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Settings size={20} color="var(--primary-light)" />
          Agent Language configuration
        </h3>
        
        <div className="input-group">
          <label>Agent Spoken & Written Language</label>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
            This controls the language the agent uses to reply in text chat and speak in live voice calls.
          </p>
          <select 
            className="input-field"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={{ width: '100%', marginBottom: '20px', padding: '10px', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(0,0,0,0.2)', color: 'white' }}
          >
            <option value="Bengali">Bengali</option>
            <option value="English">English</option>
            <option value="Spanish">Spanish</option>
            <option value="Portuguese">Portuguese</option>
          </select>
        </div>

        {message && (
          <div style={{ 
            padding: '12px', 
            borderRadius: '8px',
            marginBottom: '20px',
            background: message.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            color: message.type === 'success' ? 'var(--success)' : 'var(--danger)',
            display: 'flex', alignItems: 'center', gap: '8px'
          }}>
            {message.type === 'success' ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
            {message.text}
          </div>
        )}

        <button 
          className="btn" 
          onClick={handleSave} 
          disabled={saving}
          style={{ background: 'var(--primary)', color: 'white' }}
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, Clock, Coffee, Save, ArrowLeft, CheckCircle } from 'lucide-react';
import { motion } from 'framer-motion';

const TimesheetForm = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    locum_email: '',
    shift_date: new Date().toISOString().split('T')[0],
    scheduled_start_time: '09:00',
    scheduled_end_time: '17:00',
    actual_start_time: '09:00',
    actual_end_time: '17:00',
    scheduled_break_minutes: 60,
    actual_break_minutes: 60,
    notes: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: ['scheduled_break_minutes', 'actual_break_minutes'].includes(name) ? parseInt(value) || 0 : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    // format time string as HH:MM:00
    const payload = {
      ...formData,
      scheduled_start_time: formData.scheduled_start_time.length === 5 ? formData.scheduled_start_time + ':00' : formData.scheduled_start_time,
      scheduled_end_time: formData.scheduled_end_time.length === 5 ? formData.scheduled_end_time + ':00' : formData.scheduled_end_time,
      actual_start_time: formData.actual_start_time.length === 5 ? formData.actual_start_time + ':00' : formData.actual_start_time,
      actual_end_time: formData.actual_end_time.length === 5 ? formData.actual_end_time + ':00' : formData.actual_end_time,
    };

    try {
      const response = await fetch('/api/timesheets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      });
      
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        setSuccess(true);
      } else {
        throw new Error(data.detail || data.message || 'Failed to submit timesheet');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="app-container" style={{ overflowY: 'auto' }}>
      <div className="ambient-aurora">
        <div className="aurora-blob primary"></div>
        <div className="aurora-blob secondary"></div>
      </div>

      <header className="header">
        <div className="header-brand" style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <img src="/logo.png" alt="Unified IT Logo" className="brand-logo" />
          <h2 style={{ color: 'white', margin: 0, fontSize: '1.2rem' }}>Timesheet Submission</h2>
        </div>
        <div className="action-buttons">
          <motion.button 
            className="new-chat-btn"
            onClick={() => navigate('/')}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <ArrowLeft size={18} />
            Back to Chat
          </motion.button>
        </div>
      </header>

      <main style={{ maxWidth: '800px', margin: '40px auto', padding: '0 20px', position: 'relative', zIndex: 10 }}>
        {success ? (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{ 
              background: 'var(--surface-light)', padding: '40px', borderRadius: '16px', 
              textAlign: 'center', border: '1px solid var(--border)' 
            }}
          >
            <CheckCircle size={64} color="#10b981" style={{ margin: '0 auto 20px' }} />
            <h2 style={{ color: 'white', marginBottom: '10px' }}>Timesheet Submitted Successfully!</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '30px' }}>Your timesheet has been received and is pending approval.</p>
            <button 
              className="new-chat-btn" 
              onClick={() => {
                setSuccess(false);
                setFormData(prev => ({...prev, notes: ''}));
              }}
              style={{ padding: '12px 24px', fontSize: '1rem', margin: '0 auto' }}
            >
              Submit Another
            </button>
          </motion.div>
        ) : (
          <motion.form 
            onSubmit={handleSubmit}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ 
              background: 'var(--surface-light)', padding: '30px', borderRadius: '16px',
              border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '20px'
            }}
          >
            {error && (
              <div style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '15px', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                {error}
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '20px' }}>
              <div className="form-group">
                <label style={{ display: 'block', color: 'var(--text-main)', marginBottom: '8px' }}>Locum Email</label>
                <input 
                  type="email" 
                  name="locum_email"
                  required
                  value={formData.locum_email}
                  onChange={handleChange}
                  className="chat-input"
                  style={{ width: '100%', borderRadius: '8px', padding: '12px' }}
                  placeholder="Enter your email"
                />
              </div>

              <div className="form-group">
                <label style={{ display: 'block', color: 'var(--text-main)', marginBottom: '8px' }}>Shift Date</label>
                <input 
                  type="date" 
                  name="shift_date"
                  required
                  value={formData.shift_date}
                  onChange={handleChange}
                  className="chat-input"
                  style={{ width: '100%', borderRadius: '8px', padding: '12px' }}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '20px', borderRadius: '12px' }}>
                <h3 style={{ color: 'white', marginTop: 0, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1rem' }}>
                  <Calendar size={18} color="var(--primary-light)" /> Scheduled Hours
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginTop: '15px' }}>
                  <div>
                    <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '5px', fontSize: '0.9rem' }}>Start Time</label>
                    <input type="time" name="scheduled_start_time" required value={formData.scheduled_start_time} onChange={handleChange} className="chat-input" style={{ width: '100%', padding: '10px' }} />
                  </div>
                  <div>
                    <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '5px', fontSize: '0.9rem' }}>End Time</label>
                    <input type="time" name="scheduled_end_time" required value={formData.scheduled_end_time} onChange={handleChange} className="chat-input" style={{ width: '100%', padding: '10px' }} />
                  </div>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '5px', fontSize: '0.9rem' }}>Break (minutes)</label>
                    <input type="number" name="scheduled_break_minutes" required min="0" value={formData.scheduled_break_minutes} onChange={handleChange} className="chat-input" style={{ width: '100%', padding: '10px' }} />
                  </div>
                </div>
              </div>

              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '20px', borderRadius: '12px' }}>
                <h3 style={{ color: 'white', marginTop: 0, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1rem' }}>
                  <Clock size={18} color="#f59e0b" /> Actual Hours
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginTop: '15px' }}>
                  <div>
                    <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '5px', fontSize: '0.9rem' }}>Start Time</label>
                    <input type="time" name="actual_start_time" required value={formData.actual_start_time} onChange={handleChange} className="chat-input" style={{ width: '100%', padding: '10px', borderColor: formData.actual_start_time !== formData.scheduled_start_time ? '#f59e0b' : '' }} />
                  </div>
                  <div>
                    <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '5px', fontSize: '0.9rem' }}>End Time</label>
                    <input type="time" name="actual_end_time" required value={formData.actual_end_time} onChange={handleChange} className="chat-input" style={{ width: '100%', padding: '10px', borderColor: formData.actual_end_time !== formData.scheduled_end_time ? '#f59e0b' : '' }} />
                  </div>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '5px', fontSize: '0.9rem' }}>Break (minutes)</label>
                    <input type="number" name="actual_break_minutes" required min="0" value={formData.actual_break_minutes} onChange={handleChange} className="chat-input" style={{ width: '100%', padding: '10px', borderColor: formData.actual_break_minutes !== formData.scheduled_break_minutes ? '#f59e0b' : '' }} />
                  </div>
                </div>
              </div>
            </div>

            <div className="form-group">
              <label style={{ display: 'block', color: 'var(--text-main)', marginBottom: '8px' }}>Adjustment Notes (Reason for discrepancy)</label>
              <textarea 
                name="notes"
                value={formData.notes}
                onChange={handleChange}
                className="chat-input"
                style={{ width: '100%', borderRadius: '8px', padding: '12px', minHeight: '100px', resize: 'vertical' }}
                placeholder="E.g. Arrived 15 minutes late due to traffic, took a shorter lunch break..."
              />
            </div>

            <motion.button 
              type="submit" 
              className="new-chat-btn"
              disabled={isSubmitting}
              style={{ padding: '15px', fontSize: '1.1rem', justifyContent: 'center', marginTop: '10px' }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {isSubmitting ? 'Submitting...' : (
                <>
                  <Save size={20} />
                  Submit Timesheet
                </>
              )}
            </motion.button>
          </motion.form>
        )}
      </main>
    </div>
  );
};

export default TimesheetForm;

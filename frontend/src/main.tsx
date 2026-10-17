import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Landmark,
  Send,
  ExternalLink,
  LoaderCircle,
  RotateCcw,
  AlertCircle,
  CheckCircle2,
  Database,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import './styles.css';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

type RagChunk = {
  scheme_name: string;
  url?: string;
  score: number;
  snippet: string;
};

type Result = {
  status: string;
  is_scheme_related: boolean;
  evidence_sufficient: boolean;
  reason?: string;
  answer?: { summary: string; sections: { heading: string; content: string }[] };
  sources: { title: string; url?: string }[];
  scheme_names: string[];
  retrieved_rag_data?: RagChunk[];
};

const prompts = [
  'What schemes are available for farmers?',
  'Explain PM-KISAN eligibility.',
  'What documents are required to apply?',
  'How do I find scholarship schemes?',
];

function App() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'ready' | 'unavailable'>('checking');
  const [showRagData, setShowRagData] = useState(true);

  // Check backend health on load and periodically
  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout>;

    async function checkHealth() {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        const res = await fetch(`${API_BASE}/api/health`, { signal: controller.signal });
        clearTimeout(timeout);
        const data = await res.json();
        if (!cancelled) {
          setBackendStatus(data.rag_ready ? 'ready' : 'unavailable');
          if (!data.rag_ready) {
            retryTimer = setTimeout(checkHealth, 5000);
          }
        }
      } catch {
        if (!cancelled) {
          setBackendStatus('unavailable');
          retryTimer = setTimeout(checkHealth, 5000);
        }
      }
    }

    checkHealth();
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
    };
  }, []);

  async function submit(value = question) {
    const q = value.trim();
    if (!q) {
      setError('Please enter a question.');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 120000);

      const res = await fetch(`${API_BASE}/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
        signal: controller.signal,
      });

      clearTimeout(timeout);
      const data: Result = await res.json();

      if (!res.ok) {
        throw new Error((data as any).detail || `Server error (${res.status}). Please try again.`);
      }

      // Print RAG data to browser console
      console.log('=== DATA RETRIEVED FROM RAG MODEL ===');
      console.table(data.retrieved_rag_data || []);
      console.log('Full response:', data);

      setResult(data);
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        setError('The request timed out. The server may be busy — please try again.');
      } else if (e instanceof TypeError && e.message.includes('fetch')) {
        setError('Cannot connect to the server. Please ensure the backend is running on port 8000.');
        setBackendStatus('unavailable');
      } else {
        setError(e instanceof Error ? e.message : 'An unexpected error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header>
        <div className="brand">
          <span className="mark">
            <Landmark size={20} />
          </span>
          <div>
            <h1>Indian Government Schemes Assistant</h1>
            <p>Find scheme information using an AI-powered knowledge base</p>
          </div>
        </div>
        <div className={`status-badge ${backendStatus}`}>
          {backendStatus === 'checking' && (
            <>
              <LoaderCircle className="spin" size={14} /> Connecting…
            </>
          )}
          {backendStatus === 'ready' && (
            <>
              <CheckCircle2 size={14} /> Backend Ready
            </>
          )}
          {backendStatus === 'unavailable' && (
            <>
              <AlertCircle size={14} /> Backend Offline
            </>
          )}
        </div>
      </header>

      <section className="hero">
        <span className="eyebrow">SCHEME KNOWLEDGE BASE</span>
        <h2>How can we help you?</h2>
        <p className="intro">
          Ask about scheme eligibility, benefits, documents, or how to apply. Answers are grounded in
          the available scheme records.
        </p>

        <label htmlFor="question">Your question</label>
        <textarea
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask about eligibility, benefits, documents, or how to apply..."
          maxLength={2000}
        />

        <div className="actions">
          <span>Press Enter to send · Shift + Enter for a new line</span>
          <button onClick={() => submit()} disabled={loading}>
            {loading ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}
            Ask Question
          </button>
        </div>

        <div className="suggestions">
          {prompts.map((p) => (
            <button
              key={p}
              onClick={() => {
                setQuestion(p);
                submit(p);
              }}
              disabled={loading}
            >
              {p}
            </button>
          ))}
        </div>
      </section>

      {loading && (
        <section className="card status">
          <LoaderCircle className="spin" /> Searching the scheme knowledge base and verifying the
          retrieved information…
        </section>
      )}

      {error && (
        <section className="card error">
          <strong>Unable to complete the request</strong>
          <p>{error}</p>
          <button onClick={() => submit()}>
            <RotateCcw size={16} />
            Try again
          </button>
        </section>
      )}

      {result && (
        <>
          {/* Main Answer Card */}
          <section className={'card result ' + result.status}>
            {result.status === 'success' && result.answer && (
              <>
                <span className="eyebrow">ANSWER</span>
                <h2>{result.answer.summary}</h2>
                {result.answer.sections.map((s, i) => (
                  <article key={i}>
                    <h3>{s.heading}</h3>
                    <p>{s.content}</p>
                  </article>
                ))}
              </>
            )}

            {result.status === 'out_of_scope' && (
              <>
                <h2>This assistant focuses on Indian Government Schemes</h2>
                <p>
                  {result.reason ||
                    'Please ask about eligibility, benefits, applications, or required documents.'}
                </p>
              </>
            )}

            {result.status === 'insufficient_evidence' && (
              <>
                <h2>More supporting information is needed</h2>
                <p>
                  {result.reason ||
                    'The current knowledge base did not provide enough evidence to answer safely.'}
                </p>
              </>
            )}

            {result.scheme_names?.length > 0 && (
              <p className="schemes">
                <b>Related records:</b> {result.scheme_names.join(', ')}
              </p>
            )}

            {result.sources?.length > 0 && (
              <div className="sources">
                <h3>Sources</h3>
                {result.sources.map((s, i) =>
                  s.url ? (
                    <a key={i} href={s.url} target="_blank" rel="noreferrer">
                      {s.title}
                      <ExternalLink size={14} />
                    </a>
                  ) : (
                    <span key={i}>{s.title}</span>
                  )
                )}
              </div>
            )}

            {result.status === 'success' && (
              <p className="note">
                Scheme details can change. Verify time-sensitive information with the relevant official
                source.
              </p>
            )}
          </section>

          {/* Retrieved Data from RAG Model Section */}
          {result.retrieved_rag_data && result.retrieved_rag_data.length > 0 && (
            <section className="card rag-data-section">
              <div
                className="rag-data-header"
                onClick={() => setShowRagData(!showRagData)}
                style={{ cursor: 'pointer' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Database size={18} color="#216b70" />
                  <h3 style={{ margin: 0, fontSize: '16px', color: '#152c3e' }}>
                    Data Retrieved from Local RAG Model ({result.retrieved_rag_data.length} chunks)
                  </h3>
                </div>
                <button
                  type="button"
                  className="toggle-btn"
                  style={{ background: 'none', border: 'none', color: '#55636b', padding: '4px' }}
                >
                  {showRagData ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </button>
              </div>

              {showRagData && (
                <div className="rag-chunks-list" style={{ marginTop: '16px' }}>
                  {result.retrieved_rag_data.map((chunk, idx) => (
                    <div key={idx} className="rag-chunk-card">
                      <div className="rag-chunk-header">
                        <span className="rag-chunk-rank">#{idx + 1}</span>
                        <strong className="rag-chunk-title">
                          {chunk.url ? (
                            <a href={chunk.url} target="_blank" rel="noreferrer">
                              {chunk.scheme_name}
                              <ExternalLink size={12} style={{ marginLeft: '4px' }} />
                            </a>
                          ) : (
                            chunk.scheme_name
                          )}
                        </strong>
                        <span className="rag-chunk-score">
                          Score: {(chunk.score * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="rag-chunk-snippet">{chunk.snippet}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);

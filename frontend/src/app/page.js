'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';
import InventoryDashboard from '@/components/InventoryDashboard';
import { getApiErrorMessage } from '@/lib/apiError';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function Home() {
  const { user, loading, logout, authFetch, isAdmin } = useAuth();
  const router = useRouter();

  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [loadingBriefing, setLoadingBriefing] = useState(false);
  const [briefing, setBriefing] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [inventoryRefreshKey, setInventoryRefreshKey] = useState(0);

  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [searchError, setSearchError] = useState('');
  const [isListening, setIsListening] = useState(false);
  const speechRecognition = useRef(null);

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => setIsListening(true);
        recognition.onend = () => setIsListening(false);
        recognition.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          setSearchQuery(transcript);
        };

        speechRecognition.current = recognition;
      }
      return () => speechRecognition.current?.abort();
    }
  }, []);

  const toggleVoiceListening = () => {
    const recognition = speechRecognition.current;
    if (!recognition) return alert('Voice recognition is not supported in this browser. Try Chrome or Edge.');
    if (isListening) {
      recognition.stop();
    } else {
      recognition.start();
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return alert('Please select a CSV file first.');
    setUploading(true);
    setStatusMessage('');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await authFetch(`${API_URL}/inventory/upload-csv`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setStatusMessage('Inventory CSV successfully imported!');
        setInventoryRefreshKey((key) => key + 1);
      }
      else setStatusMessage(`Error: ${getApiErrorMessage(data, 'Upload failed')}`);
    } catch (err) {
      setStatusMessage('Network error connecting to backend.');
    } finally {
      setUploading(false);
    }
  };

  const fetchBriefing = async () => {
    setLoadingBriefing(true);
    setBriefing('');
    try {
      const res = await authFetch(`${API_URL}/analytics/morning-briefing`);
      const data = await res.json();
      if (res.ok) setBriefing(data.briefing);
      else setBriefing(getApiErrorMessage(data, 'Failed to retrieve AI data metrics.'));
    } catch (err) {
      setBriefing('Network error retrieving data.');
    } finally {
      setLoadingBriefing(false);
    }
  };

  const handleNaturalSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery || !searchQuery.trim()) return;
    setSearching(true);
    setSearchResults(null);
    setSearchError('');

    try {
      const res = await authFetch(`${API_URL}/query/ask?q=${encodeURIComponent(searchQuery)}`);
      const data = await res.json();
      if (res.ok) {
        setSearchResults(data);
      } else {
        setSearchError(getApiErrorMessage(data, 'Query extraction error.'));
      }
    } catch (err) {
      setSearchError('Network error querying AI engine.');
    } finally {
      setSearching(false);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 flex items-center justify-center">
        <p className="text-slate-400">Loading...</p>
      </main>
    );
  }

  if (!user) return null;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 font-sans">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header Block */}
        <header className="border-b border-slate-800 pb-6 flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                RxOS - AI Pharmacy Operating System
              </h1>
              {isAdmin && (
                <Link href="/admin" className="px-2 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded border border-amber-500/30 hover:bg-amber-500/30">
                  Admin
                </Link>
              )}
            </div>
            <p className="text-slate-400 mt-2">Intelligent operations, inventory prediction, and risk mitigation.</p>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/sales" className="px-3 py-1 text-sm text-emerald-300 border border-emerald-500/30 rounded-md hover:bg-emerald-500/10">
              Sales
            </Link>
            <Link href="/purchasing" className="px-3 py-1 text-sm text-cyan-300 border border-cyan-500/30 rounded-md hover:bg-cyan-500/10">
              Purchasing
            </Link>
            <span className="text-sm text-slate-400">
              {user.full_name || user.email}
              <span className="ml-2 text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400">{user.role}</span>
            </span>
            <button
              onClick={logout}
              className="px-3 py-1 text-sm text-slate-400 hover:text-slate-200 border border-slate-700 rounded-md hover:bg-slate-800 transition-colors"
            >
              Sign Out
            </button>
          </div>
        </header>

        <InventoryDashboard authFetch={authFetch} refreshKey={inventoryRefreshKey} />

        {/* Data Ingestion Panel */}
        <section className="bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-xl">
          <h2 className="text-xl font-semibold text-slate-200 mb-4">Import inventory CSV</h2>
          <form onSubmit={handleUpload} className="flex flex-col sm:flex-row gap-4 items-center">
            <input 
              type="file" accept=".csv"
              onChange={(e) => setFile(e.target.files[0])}
              className="block w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-emerald-500/10 file:text-emerald-400 hover:file:bg-emerald-500/20 cursor-pointer"
            />
            <button type="submit" disabled={uploading} className="w-full sm:w-auto px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white font-medium rounded-md transition-colors">
              {uploading ? 'Processing...' : 'Upload CSV'}
            </button>
          </form>
          {statusMessage && <p className="mt-4 text-sm font-medium">{statusMessage}</p>}
        </section>

        {/* Conversational AI Explorer Box */}
        <section className="bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-xl space-y-4">
          <h2 className="text-xl font-semibold text-slate-200">Conversational Database Explorer (Type or Speak)</h2>
          <form onSubmit={handleNaturalSearch} className="flex gap-2">
            <div className="relative flex-1">
              <input 
                type="text"
                placeholder='Ask anything... e.g., "Show me antibiotics running low" or "Find paracetamol"'
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-md py-2 pl-4 pr-12 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <button
                type="button"
                onClick={toggleVoiceListening}
                className={`absolute right-2 top-1.5 p-1 rounded-md transition-colors ${isListening ? 'bg-red-500/20 text-red-400 animate-pulse' : 'text-slate-400 hover:bg-slate-800'}`}
                title="Speak command"
              >
                Mic
              </button>
            </div>
            <button type="submit" disabled={searching} className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white font-medium rounded-md text-sm transition-colors">
              {searching ? 'Querying...' : 'Ask'}
            </button>
          </form>

          {searchError && (
            <div role="alert" className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {searchError}
            </div>
          )}

          {/* Results Render Box */}
          {searchResults && (
            <div className="mt-4 space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-850">
              <div className="text-xs text-slate-500 font-mono mb-2">
                SQL Run: {searchResults.query_generated}
              </div>
              {searchResults.data.length === 0 ? (
                <p className="text-sm text-slate-400 italic">No matching items found inside the database pool.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm text-slate-300">
                    <thead className="text-xs uppercase bg-slate-900 text-slate-400">
                      <tr>
                        {Object.keys(searchResults.data[0]).map((key) => (
                          <th key={key} className="px-4 py-2 border-b border-slate-800">{key}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {searchResults.data.map((row, idx) => (
                        <tr key={idx} className="hover:bg-slate-900/50">
                          {Object.values(row).map((val, i) => (
                            <td key={i} className="px-4 py-2 border-b border-slate-850 max-w-xs truncate">{String(val)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>

        {/* AI Briefing Output Interface */}
        <section className="bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-xl space-y-4">
          <div className="flex justify-between items-center border-b border-slate-800 pb-4">
            <h2 className="text-xl font-semibold text-slate-200">AI Operations Briefing</h2>
            <button onClick={fetchBriefing} disabled={loadingBriefing} className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white font-medium rounded-md transition-colors text-sm">
              {loadingBriefing ? 'Analyzing Data...' : 'Generate Live Insights'}
            </button>
          </div>

          <div className="min-h-[150px] bg-slate-950 rounded-lg p-6 border border-slate-850 text-slate-300 leading-relaxed whitespace-pre-wrap">
            {briefing ? (
              <div className="prose prose-invert max-w-none tracking-wide space-y-2">
                <ReactMarkdown>{briefing}</ReactMarkdown>
              </div>
            ) : (
              <p className="text-slate-500 italic text-center pt-12">Click &quot;Generate Live Insights&quot; to analyze current pharmacy operations with Groq AI.</p>
            )}
          </div>
        </section>

      </div>
    </main>
  );
}

'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';
import InventoryDashboard from '@/components/InventoryDashboard';
import DashboardSidebar from '@/components/DashboardSidebar';
import AppIcon from '@/components/AppIcon';
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
      <main className="flex min-h-screen items-center justify-center bg-[#f5f7fa]">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-teal-600" />
          <p className="mt-3 text-sm font-medium text-slate-500">Loading your pharmacy workspace…</p>
        </div>
      </main>
    );
  }

  if (!user) return null;

  return (
    <DashboardSidebar user={user} isAdmin={isAdmin} onLogout={logout}>
      <main className="app-content px-4 py-6 md:px-7 md:py-7">
        <div className="mx-auto max-w-[1440px] space-y-7">
          <section className="flex flex-col justify-between gap-5 border-b border-slate-200 pb-6 md:flex-row md:items-end">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Pharmacy overview</h1>
              <p className="mt-1.5 max-w-2xl text-sm text-slate-500">Monitor stock health, act on inventory risks, and continue daily operations.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href="/purchasing" className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">
                <AppIcon name="purchasing" className="h-4 w-4" /> Purchase order
              </Link>
              <Link href="/sales" className="inline-flex items-center gap-2 rounded-lg bg-[#18324b] px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-[#10263a]">
                <AppIcon name="plus" className="h-4 w-4" /> New sale
              </Link>
            </div>
          </section>

          <InventoryDashboard authFetch={authFetch} refreshKey={inventoryRefreshKey} />

          <div className="grid gap-5 xl:grid-cols-[1.45fr_0.8fr]">
            <section className="glass-panel rounded-lg border border-white/80">
              <div className="border-b border-slate-200 px-5 py-4">
                <h2 className="text-sm font-semibold text-slate-900">Inventory assistant</h2><p className="mt-0.5 text-xs text-slate-500">Search your stock using plain language.</p>
              </div>
              <form onSubmit={handleNaturalSearch} className="flex flex-col gap-2 p-5 sm:flex-row">
                <div className="relative flex-1">
                  <AppIcon name="search" className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-slate-400" />
                  <input type="text" placeholder='Try “show medicines running low”' value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-10 pr-16 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-[#18324b] focus:ring-2 focus:ring-[#dce7f0]" />
                  <button type="button" onClick={toggleVoiceListening} className={`absolute right-2 top-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-semibold transition ${isListening ? 'bg-rose-100 text-rose-600' : 'text-slate-500 hover:bg-slate-100'}`} title="Speak command">{isListening ? 'Listening' : 'Speak'}</button>
                </div>
                <button type="submit" disabled={searching} className="rounded-lg bg-[#18324b] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#10263a] disabled:opacity-50">{searching ? 'Searching…' : 'Search'}</button>
              </form>
              {searchError && <div role="alert" className="mx-5 mb-5 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{searchError}</div>}
              {searchResults && (
                <div className="mx-5 mb-5 overflow-hidden rounded-lg border border-slate-200">
                  {searchResults.data.length === 0 ? <p className="p-5 text-sm text-slate-500">No matching inventory was found.</p> : (
                    <div className="overflow-x-auto"><table className="w-full text-left text-sm text-slate-700"><thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500"><tr>{Object.keys(searchResults.data[0]).map((key) => <th key={key} className="border-b border-slate-200 px-4 py-3">{key}</th>)}</tr></thead><tbody>{searchResults.data.map((row, idx) => <tr key={idx} className="border-b border-slate-100 last:border-0">{Object.values(row).map((val, i) => <td key={i} className="max-w-xs truncate px-4 py-3">{String(val)}</td>)}</tr>)}</tbody></table></div>
                  )}
                </div>
              )}
            </section>

            <section className="glass-panel rounded-lg border border-white/80">
              <div className="border-b border-slate-200 px-5 py-4">
                <h2 className="text-sm font-semibold text-slate-900">Import inventory</h2><p className="mt-0.5 text-xs text-slate-500">Add stock from a prepared CSV file.</p>
              </div>
              <form onSubmit={handleUpload} className="space-y-3 p-5">
                <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0])} className="block w-full rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 text-sm text-slate-500 file:mr-3 file:rounded-md file:border-0 file:bg-white file:px-3 file:py-2 file:text-xs file:font-semibold file:text-[#18324b] hover:border-slate-400" />
                <button type="submit" disabled={uploading} className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50">{uploading ? 'Importing…' : 'Upload CSV'}</button>
              </form>
              {statusMessage && <p className="px-5 pb-5 text-sm font-medium text-slate-600">{statusMessage}</p>}
            </section>
          </div>

          <section className="glass-panel overflow-hidden rounded-lg border border-white/80">
            <div className="flex flex-col justify-between gap-4 border-b border-slate-200 p-5 sm:flex-row sm:items-center md:px-6">
              <div><h2 className="text-sm font-semibold text-slate-900">Operations briefing</h2><p className="mt-0.5 text-xs text-slate-500">Generate a concise review of stock and expiry priorities.</p></div>
              <button onClick={fetchBriefing} disabled={loadingBriefing} className="rounded-lg bg-[#18324b] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#10263a] disabled:opacity-50">{loadingBriefing ? 'Analyzing…' : 'Generate briefing'}</button>
            </div>
            <div className="min-h-40 p-5 text-sm leading-7 text-slate-700 md:p-6">
              {briefing ? <div className="prose max-w-none"><ReactMarkdown>{briefing}</ReactMarkdown></div> : <div className="grid min-h-28 place-items-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-center text-slate-500"><p>Generate a live briefing when you are ready to review operations.</p></div>}
            </div>
          </section>
        </div>
      </main>
    </DashboardSidebar>
  );
}

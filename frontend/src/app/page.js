'use client';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

export default function Home() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [loadingBriefing, setLoadingBriefing] = useState(false);
  const [briefing, setBriefing] = useState('');
  const [statusMessage, setStatusMessage] = useState('');

  // 1. Handle File Upload to FastAPI Backend
  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return alert('Please select a CSV file first.');

    setUploading(true);
    setStatusMessage('');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('http://127.0.0.1:8000/inventory/upload-csv', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setStatusMessage('✅ Inventory CSV successfully imported to cloud!');
      } else {
        setStatusMessage(`❌ Error: ${data.detail || 'Upload failed'}`);
      }
    } catch (err) {
      setStatusMessage('❌ Network error connecting to backend.');
    } finally {
      setUploading(false);
    }
  };

  // 2. Fetch AI Insights from Backend
  const fetchBriefing = async () => {
    setLoadingBriefing(true);
    setBriefing('');
    try {
      const res = await fetch('http://127.0.0.1:8000/analytics/morning-briefing');
      const data = await res.json();
      if (res.ok) {
        setBriefing(data.briefing);
      } else {
        setBriefing('Failed to retrieve AI data metrics.');
      }
    } catch (err) {
      setBriefing('Network error retrieving data.');
    } finally {
      setLoadingBriefing(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Header Block */}
        <header className="border-b border-slate-800 pb-6">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
            RxOS • AI Pharmacy Operating System
          </h1>
          <p className="text-slate-400 mt-2">Intelligent operations, inventory prediction, and risk mitigation.</p>
        </header>

        {/* Data Ingestion Panel */}
        <section className="bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-xl">
          <h2 className="text-xl font-semibold text-slate-200 mb-4">1. Import Legacy Sales/Inventory</h2>
          <form onSubmit={handleUpload} className="flex flex-col sm:flex-row gap-4 items-center">
            <input 
              type="file" 
              accept=".csv"
              onChange={(e) => setFile(e.target.files[0])}
              className="block w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-emerald-500/10 file:text-emerald-400 hover:file:bg-emerald-500/20 cursor-pointer"
            />
            <button 
              type="submit" 
              disabled={uploading}
              className="w-full sm:w-auto px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white font-medium rounded-md transition-colors"
            >
              {uploading ? 'Processing...' : 'Upload CSV'}
            </button>
          </form>
          {statusMessage && <p className="mt-4 text-sm font-medium">{statusMessage}</p>}
        </section>

        {/* AI Briefing Output Interface */}
        <section className="bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-xl space-y-4">
          <div className="flex justify-between items-center border-b border-slate-800 pb-4">
            <h2 className="text-xl font-semibold text-slate-200">2. Active AI Strategy Briefing</h2>
            <button 
              onClick={fetchBriefing}
              disabled={loadingBriefing}
              className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white font-medium rounded-md transition-colors text-sm"
            >
              {loadingBriefing ? 'Analyzing Data...' : 'Generate Live Insights'}
            </button>
          </div>

          <div className="min-h-[200px] bg-slate-950 rounded-lg p-6 border border-slate-850 text-slate-300 leading-relaxed whitespace-pre-wrap">
            {briefing ? (
              <div className="prose prose-invert max-w-none tracking-wide space-y-2">
              <ReactMarkdown>{briefing}</ReactMarkdown>
</div>
            ) : (
              <p className="text-slate-500 italic text-center pt-16">
                Click "Generate Live Insights" to stream real-time analysis from Llama 3.3.
              </p>
            )}
          </div>
        </section>

      </div>
    </main>
  );
}
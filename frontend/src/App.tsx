import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

function App() {
  const [url, setUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [summary, setSummary] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSummarize = async () => {
    if (!url.trim()) {
      setError('Please enter a GitHub repository URL');
      return;
    }

    setLoading(true);
    setError('');
    setSummary('');

    try {
      const body: Record<string, string> = { url: url.trim() };
      if (apiKey.trim()) body.api_key = apiKey.trim();

      const res = await fetch('http://localhost:8000/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `Request failed (${res.status})`);
      }

      const data = await res.json();
      setSummary(data.summary);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#edf4f1] flex flex-col">
      {/* Header */}
      <header className="w-full bg-white py-5 px-6 md:px-12 shadow-[0px_1px_0px_0px_#e9e9e9]">
        <div className="w-full max-w-[1400px] mx-auto flex items-center justify-between">
          <span className="font-['DM_Sans'] font-medium text-[28px] text-black tracking-[-1.5px]">
            RepoSummarizer
          </span>
          <span className="font-['Roboto_Mono'] text-[13px] text-[#485c11] tracking-[-0.12px] bg-[#dfecc6] px-4 py-1.5 rounded-full">
            AI-Powered
          </span>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 flex flex-col items-center px-6 md:px-12 pt-20 pb-32">
        <div className="w-full max-w-[1400px] flex flex-col items-center">

          {/* Title */}
          <h1 className="font-['Crimson_Text'] font-normal text-black text-center tracking-[-4px] leading-[0.95] text-[72px] sm:text-[100px] lg:text-[140px] mb-8">
            Summarize.
          </h1>

          <p className="font-['DM_Sans'] text-[20px] sm:text-[22px] text-[#6f6f6f] tracking-[-0.3px] leading-[1.6] text-center max-w-[620px] mb-20">
            Paste a GitHub repository URL and get an AI-generated summary of the project — its purpose, tech stack, architecture, and more.
          </p>

          {/* Input Card */}
          <div
            className="w-full max-w-[860px] bg-white rounded-[30px] flex flex-col shadow-[0px_4px_40px_0px_rgba(0,0,0,0.06)]"
            style={{ padding: '50px 60px', marginTop: '50px', marginBottom: '50px' }}
          >
            <div className="flex flex-col gap-8" style={{ padding: '10px' }}>

              {/* URL Input */}
              <div className="flex flex-col gap-3">
                <label className="font-['Roboto_Mono'] text-[14px] text-[#485c11] tracking-[-0.12px] leading-[1.4] font-medium">
                  Repository URL
                </label>
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
className="w-full h-[60px] rounded-[16px] border border-[#e0e0e0] bg-[#fafafa] font-['DM_Sans'] text-[17px] text-black tracking-[-0.2px] placeholder:text-[#b0b0b0] focus:outline-none focus:border-[#485c11] focus:ring-2 focus:ring-[#dfecc6] focus:bg-white transition-all"
                  style={{ paddingLeft: '20px', paddingRight: '20px' }}
              />
            </div>

              {/* API Key Input */}
              <div className="flex flex-col gap-3">
                <label className="font-['Roboto_Mono'] text-[14px] text-[#485c11] tracking-[-0.12px] leading-[1.4] font-medium">
                  OpenAI API Key (model: gpt-4o)
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full h-[60px] rounded-[16px] border border-[#e0e0e0] bg-[#fafafa] font-['DM_Sans'] text-[17px] text-black tracking-[-0.2px] placeholder:text-[#b0b0b0] focus:outline-none focus:border-[#485c11] focus:ring-2 focus:ring-[#dfecc6] focus:bg-white transition-all"
                  style={{ paddingLeft: '20px', paddingRight: '20px' }}
                />
                <span className="font-['DM_Sans'] text-[14px] text-[#929292] tracking-[-0.075px]">
                  Optional — falls back to server key if not provided
                </span>
              </div>

              {/* Button */}
              <button
                onClick={handleSummarize}
                disabled={loading}
                className="mt-2 w-full h-[62px] rounded-[1000px] bg-[#485c11] text-white font-['DM_Sans'] font-bold text-[17px] tracking-[-0.35px] leading-[1.4] cursor-pointer hover:bg-[#5a7218] active:scale-[0.99] disabled:opacity-60 disabled:cursor-not-allowed transition-all shadow-[0px_2px_12px_0px_rgba(72,92,17,0.3)]"
              >
                {loading ? 'Analyzing repository...' : 'Summarize Repository'}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-8 w-full max-w-[860px] rounded-[16px] bg-red-50 border border-red-200 px-8 py-5">
              <p className="font-['DM_Sans'] text-[16px] text-red-600">{error}</p>
            </div>
          )}

          {/* Loading Animation */}
          {loading && (
            <div className="mt-14 w-full flex flex-col items-center gap-5">
              <div className="w-10 h-10 rounded-full border-[3px] border-[#dfecc6] border-t-[#485c11] animate-spin" />
              <p className="font-['Roboto_Mono'] text-[14px] text-[#929292] tracking-[-0.12px]">
                Cloning and analyzing repository...
              </p>
            </div>
          )}

          {/* Summary Output */}
          {summary && (
            <div className="w-full max-w-[860px]" style={{ marginTop: '20px' }}>
              <div className="w-full bg-white rounded-[30px] shadow-[0px_4px_40px_0px_rgba(0,0,0,0.06)]" style={{ padding: '50px 60px' }}>
                <h2 className="font-['Crimson_Text'] text-[32px] text-black tracking-[-1px] leading-[1]" style={{ marginBottom: '4px' }}>
                  Summary
                </h2>
                <div className="bg-[#e9e9e9]" style={{ height: '1px', marginBottom: '32px' }} />
                <div className="summary-content font-['DM_Sans'] text-[16px] text-[#3a3a3a] tracking-[-0.1px] leading-[1.8]">
                  <ReactMarkdown>{summary.replace(/^#{1,3}\s+.+\n*/m, '')}</ReactMarkdown>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full bg-white py-6 px-6 md:px-12 shadow-[0px_-1px_0px_0px_#e9e9e9]">
        <div className="w-full max-w-[1400px] mx-auto flex items-center justify-between">
          <span className="font-['Roboto_Mono'] text-[13px] text-[#929292] tracking-[-0.12px]" style={{ paddingLeft: '55px' }}>
            GitHub Repo Summarizer
          </span>
          <span className="font-['Roboto_Mono'] text-[13px] text-[#929292] tracking-[-0.12px]">
            Created by David Shaer
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;

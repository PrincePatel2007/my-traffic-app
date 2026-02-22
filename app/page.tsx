"use client";
import React, { useState } from 'react';
import { Zap, Play, Activity, AlertTriangle, TrendingDown, Clock, Car, Siren } from 'lucide-react';

export default function TrafficDashboard() {
  // --- STATE ---
  const [totalCycles, setTotalCycles] = useState(50);
  const [avgCarTime, setAvgCarTime] = useState(5);
  const [arrivals, setArrivals] = useState({ North: [2, 12], South: [2, 12], East: [5, 15], West: [5, 15] });
  const [evProbs, setEvProbs] = useState({ North: 5, South: 5, East: 5, West: 5 });
  
  const [aiLogs, setAiLogs] = useState<any[]>([]);
  const [fxLogs, setFxLogs] = useState<any[]>([]);
  const [metrics, setMetrics] = useState({ aiLoss: 0, fxLoss: 0, gain: 0 });
  const [isSimulating, setIsSimulating] = useState(false);
  const [progress, setProgress] = useState(0);

  // --- SIMULATION ENGINE ---
  const runSimulation = async () => {
    setIsSimulating(true);
    setAiLogs([]);
    setFxLogs([]);
    setProgress(0);
    setMetrics({ aiLoss: 0, fxLoss: 0, gain: 0 });

    try {
      const response = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          total_cycles: totalCycles,
          avg_car_time: avgCarTime,
          arrival_ranges: arrivals,
          ev_probs: {
            North: evProbs.North / 100,
            South: evProbs.South / 100,
            East: evProbs.East / 100,
            West: evProbs.West / 100
          }
        })
      });

      const data = await response.json();
      
      // Safety check to ensure arrays exist
      if (!data.ai_logs || !data.fx_logs) {
        throw new Error("Invalid data received from Python API.");
      }

      // Find the exact limit to prevent Out-Of-Bounds array crashes
      const maxItems = Math.min(data.ai_logs.length, data.fx_logs.length);
      
      let i = 0;
      const interval = setInterval(() => {
        try {
          // If we hit the end of the arrays, cleanly stop the animation
          if (i >= maxItems) {
            clearInterval(interval);
            setIsSimulating(false);
            setProgress(100);
            return;
          }

          const aiRow = data.ai_logs[i];
          const fxRow = data.fx_logs[i];

          // Safely prepend the new row
          if (aiRow && fxRow) {
            setAiLogs(prev => [aiRow, ...prev]);
            setFxLogs(prev => [fxRow, ...prev]);
          }
          
          // Calculate live metrics safely
          const currentAiLoss = data.ai_logs.slice(0, i + 1).reduce((acc: number, row: any) => acc + (row?.["Cycle Loss"] || 0), 0);
          const currentFxLoss = data.fx_logs.slice(0, i + 1).reduce((acc: number, row: any) => acc + (row?.["Cycle Loss"] || 0), 0);
          const currentGain = currentFxLoss > 0 ? ((currentFxLoss - currentAiLoss) / currentFxLoss) * 100 : 0;
          
          setMetrics({ aiLoss: currentAiLoss, fxLoss: currentFxLoss, gain: currentGain });
          setProgress(Math.round(((i + 1) / maxItems) * 100));
          
          i++;
        } catch (err) {
          console.error("Animation rendering error:", err);
          clearInterval(interval);
          setIsSimulating(false);
        }
      }, 100); 
    } catch (error) {
      console.error("Simulation failed:", error);
      setIsSimulating(false);
      alert("Error connecting to the Python backend. Make sure the API is running!");
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* SIDEBAR */}
      <div className="w-80 bg-white border-r border-slate-200 p-6 overflow-y-auto h-screen sticky top-0 shadow-sm z-10">
        <h2 className="text-2xl font-black flex items-center gap-2 mb-8 text-indigo-600 tracking-tight">
          <Activity className="text-indigo-600" size={28} /> Control Panel
        </h2>
        
        <div className="space-y-8 text-sm">
          <div>
            <label className="flex items-center justify-between font-bold mb-2 text-slate-700">
              <span className="flex items-center gap-2"><Clock size={16} /> Total Cycles</span>
              <span className="bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded text-xs">{totalCycles}</span>
            </label>
            <input type="range" min="10" max="200" value={totalCycles} onChange={(e) => setTotalCycles(Number(e.target.value))} className="w-full accent-indigo-600" />
          </div>

          <div className="border-t border-slate-100 pt-6">
            <h3 className="font-bold mb-4 flex items-center gap-2 text-slate-700">
              <Car size={16} /> Arrivals per cycle (Min-Max)
            </h3>
            {['North', 'South', 'East', 'West'].map(lane => (
              <div key={lane} className="mb-3 flex items-center justify-between">
                <label className="block text-xs uppercase font-bold text-slate-500 w-16">{lane}</label>
                <div className="flex gap-2">
                  <input type="number" value={(arrivals as any)[lane][0]} onChange={(e) => setArrivals({...arrivals, [lane]: [Number(e.target.value), (arrivals as any)[lane][1]]})} className="w-16 border border-slate-300 rounded-md p-1.5 text-center focus:ring-2 focus:ring-indigo-500 outline-none" />
                  <span className="text-slate-400 self-center">-</span>
                  <input type="number" value={(arrivals as any)[lane][1]} onChange={(e) => setArrivals({...arrivals, [lane]: [(arrivals as any)[lane][0], Number(e.target.value)]})} className="w-16 border border-slate-300 rounded-md p-1.5 text-center focus:ring-2 focus:ring-indigo-500 outline-none" />
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-slate-100 pt-6">
            <label className="flex items-center justify-between font-bold mb-2 text-slate-700">
              <span>Avg Time / Vehicle</span>
              <span className="bg-slate-100 px-2 py-0.5 rounded text-xs">{avgCarTime}s</span>
            </label>
            <input type="range" min="2" max="10" value={avgCarTime} onChange={(e) => setAvgCarTime(Number(e.target.value))} className="w-full accent-indigo-600" />
          </div>

          <div className="border-t border-slate-100 pt-6">
            <h3 className="font-bold mb-4 flex items-center gap-2 text-slate-700">
              <Siren size={16} className="text-red-500" /> EV Probability (%)
            </h3>
            {['North', 'South', 'East', 'West'].map(lane => (
              <div key={lane} className="mb-3">
                <label className="flex justify-between text-xs font-bold text-slate-500 mb-1">
                  <span>{lane}</span>
                  <span>{(evProbs as any)[lane]}%</span>
                </label>
                <input type="range" min="0" max="100" value={(evProbs as any)[lane]} onChange={(e) => setEvProbs({...evProbs, [lane]: Number(e.target.value)})} className="w-full accent-red-500" />
              </div>
            ))}
          </div>

          <button 
            onClick={runSimulation}
            disabled={isSimulating}
            className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold hover:bg-slate-800 transition disabled:bg-slate-300 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-md mt-8"
          >
            {isSimulating ? (
              <span className="animate-pulse flex items-center gap-2">Simulating ({progress}%)</span>
            ) : (
              <><Play size={18} fill="currentColor" /> Launch Simulation</>
            )}
          </button>
        </div>
      </div>

      {/* MAIN DASHBOARD */}
      <div className="flex-1 p-10 overflow-x-hidden">
        <header className="mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-sm font-bold mb-4">
            <Zap size={14} fill="currentColor" /> Parallel Universe Engine
          </div>
          <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">Smart City Traffic AI</h1>
          <p className="text-slate-500 mt-2 max-w-2xl text-lg">Comparing real-time Adaptive AI Signal Control against Fixed Manual Timers with Emergency Vehicle Preemption.</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <MetricCard title="Fixed System Inefficiency" value={metrics.fxLoss.toLocaleString()} icon={<AlertTriangle size={20} />} color="text-red-600" bgColor="bg-red-50" borderColor="border-red-100" />
          <MetricCard title="AI System Inefficiency" value={metrics.aiLoss.toLocaleString()} icon={<Zap size={20} />} color="text-emerald-600" bgColor="bg-emerald-50" borderColor="border-emerald-100"
            subLabel={`Saved ${Math.max(0, metrics.fxLoss - metrics.aiLoss).toLocaleString()} pts`} />
          <MetricCard title="Total Efficiency Gain" value={`${metrics.gain.toFixed(1)}%`} icon={<TrendingDown size={20} />} color="text-indigo-600" bgColor="bg-indigo-50" borderColor="border-indigo-100" />
        </div>

        <div className="grid 2xl:grid-cols-2 gap-8 items-start">
          <section>
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2 text-emerald-700">
              <span className="bg-emerald-100 p-1.5 rounded-lg"><Zap size={18} /></span> AI Optimized Log
            </h2>
            <DataTable data={aiLogs} />
          </section>

          <section>
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2 text-slate-700">
              <span className="bg-slate-200 p-1.5 rounded-lg"><Clock size={18} /></span> Fixed Manual Log
            </h2>
            <DataTable data={fxLogs} />
          </section>
        </div>
      </div>
    </div>
  );
}

// --- SUB-COMPONENTS ---
function MetricCard({ title, value, color, bgColor, borderColor, icon, subLabel }: any) {
  return (
    <div className={`p-6 rounded-2xl shadow-sm border ${borderColor} bg-white flex flex-col`}>
      <div className="flex items-center gap-2 text-slate-500 mb-3 font-semibold text-sm uppercase tracking-wide">
        {React.cloneElement(icon, { className: color })} {title}
      </div>
      <div className="flex items-end justify-between mt-auto">
        <h3 className={`text-4xl font-black ${color} tracking-tight`}>{value}</h3>
        {subLabel && (
          <span className={`text-xs font-bold ${color} ${bgColor} px-2.5 py-1 rounded-full border ${borderColor}`}>
            {subLabel}
          </span>
        )}
      </div>
    </div>
  );
}

function DataTable({ data }: { data: any[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white border border-slate-200 border-dashed rounded-xl h-64 flex items-center justify-center text-slate-400 font-medium">
        Awaiting simulation data...
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden relative">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold text-xs uppercase tracking-wider sticky top-0">
            <tr>
              <th className="px-5 py-4">Phase</th>
              <th className="px-5 py-4">Queue</th>
              <th className="px-5 py-4">Timing (Alloc ➡️ Used)</th>
              <th className="px-5 py-4 text-right">Loss</th>
              <th className="px-5 py-4">Events</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.slice(0, 15).map((row, idx) => {
              // Extra safety boundary: Ignore broken rows
              if (!row) return null; 
              
              return (
                <tr key={idx} className="hover:bg-slate-50 transition-colors bg-white animate-in fade-in duration-300">
                  <td className="px-5 py-3 font-medium text-slate-900">
                    <span className="text-slate-400 text-xs mr-2">C{row?.Cycle}</span> 
                    {row?.["Phase Sequence"]}
                  </td>
                  <td className="px-5 py-3 font-medium">
                    {/* Optional chaining on string parsing prevents crashes */}
                    {row?.Queue?.toString()?.includes("🛑") ? (
                      <span className="text-red-600 animate-pulse">{row.Queue}</span>
                    ) : (
                      row?.Queue
                    )}
                  </td>
                  <td className="px-5 py-3 font-mono text-indigo-600 text-xs bg-indigo-50/50 rounded">{row?.["Allocated ➡️ Used"]}</td>
                  <td className="px-5 py-3 font-bold text-slate-700 text-right">{row?.["Cycle Loss"]}</td>
                  <td className="px-5 py-3 text-xs text-slate-500 max-w-[200px] truncate" title={row?.Events}>
                    {row?.Events}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {data.length > 15 && (
        <div className="bg-slate-50 text-center py-2 text-xs font-bold text-slate-400 border-t border-slate-200">
          Showing 15 most recent phases ({data.length} total)
        </div>
      )}
    </div>
  );
}
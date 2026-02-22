"use client";
import React, { useState } from 'react';
import { Zap, Activity, AlertTriangle, TrendingDown, Clock, Car, Siren, LayoutList, Columns, Timer, GitMerge, Gauge } from 'lucide-react';

export default function TrafficDashboard() {
  const [totalCycles, setTotalCycles] = useState(50);
  const [avgCarTime, setAvgCarTime] = useState(2.5);
  const [lanes, setLanes] = useState({ NS: 3, EW: 3 });
  
  const [arrivalsPerMin, setArrivalsPerMin] = useState({ North: [1, 4], South: [1, 4], East: [2, 5], West: [2, 5] });
  const [fxTimes, setFxTimes] = useState({ North: 45, South: 45, East: 60, West: 60 });
  const [evProbs, setEvProbs] = useState({ North: 5, South: 5, East: 5, West: 5 });
  
  const [aiLogs, setAiLogs] = useState<any[]>([]);
  const [fxLogs, setFxLogs] = useState<any[]>([]);
  const [metrics, setMetrics] = useState({ aiLoss: 0, fxLoss: 0, gain: 0 });
  const [isSimulating, setIsSimulating] = useState(false);
  const [isDetailedView, setIsDetailedView] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  const calculateCapacity = () => {
    const totalAvgArrivals = 
      ((arrivalsPerMin.North[0] + arrivalsPerMin.North[1]) / 2) +
      ((arrivalsPerMin.South[0] + arrivalsPerMin.South[1]) / 2) +
      ((arrivalsPerMin.East[0] + arrivalsPerMin.East[1]) / 2) +
      ((arrivalsPerMin.West[0] + arrivalsPerMin.West[1]) / 2);
    
    const avgLanes = (lanes.NS * 2 + lanes.EW * 2) / 4;
    const maxClearancePerMin = ((60 / avgCarTime) * 0.63) * avgLanes; 
    const saturationRatio = (totalAvgArrivals / maxClearancePerMin) * 100;
    
    return { ratio: saturationRatio, limit: maxClearancePerMin, demand: totalAvgArrivals };
  };

  const cap = calculateCapacity();

  const runSimulation = async () => {
    if (isSimulating) return;
    setIsSimulating(true); setAiLogs([]); setFxLogs([]); setMetrics({ aiLoss: 0, fxLoss: 0, gain: 0 }); setSimError(null);
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000); 
    
    try {
      const response = await fetch('/api/simulate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ total_cycles: totalCycles, avg_car_time: avgCarTime, arrivals_per_min: arrivalsPerMin, lanes: lanes, fx_times: fxTimes, ev_probs: { North: evProbs.North / 100, South: evProbs.South / 100, East: evProbs.East / 100, West: evProbs.West / 100 } }),
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      let data;
      try {
        data = await response.json();
      } catch (parseError) {
        throw new Error("Server crashed or returned an invalid response.");
      }

      if (!response.ok || data.error) { throw new Error(data.error || "Simulation failed."); }
      if (!data.ai_logs) throw new Error("Invalid data format received.");

      let i = 0;
      const chunkSize = 4; 
      const interval = setInterval(() => {
        if (i >= data.ai_logs.length) { clearInterval(interval); setIsSimulating(false); return; }
        
        const nextI = Math.min(i + chunkSize, data.ai_logs.length);
        const newAiLogs = data.ai_logs.slice(i, nextI);
        const newFxLogs = data.fx_logs.slice(i, nextI);

        setAiLogs(prev => [...newAiLogs.reverse(), ...prev]);
        setFxLogs(prev => [...newFxLogs.reverse(), ...prev]);
        
        const aiL = data.ai_logs.slice(0, nextI).reduce((acc: number, row: any) => acc + (row?.["Cycle Loss"] || 0), 0);
        const fxL = data.fx_logs.slice(0, nextI).reduce((acc: number, row: any) => acc + (row?.["Cycle Loss"] || 0), 0);
        setMetrics({ aiLoss: aiL, fxLoss: fxL, gain: fxL > 0 ? ((fxL - aiL) / fxL) * 100 : 0 });
        i = nextI;
      }, 50); 
      
    } catch (error: any) { 
      clearTimeout(timeoutId);
      setIsSimulating(false); 
      if (error.name === 'AbortError') {
          setSimError("⏳ Connection Timed Out: The AI generated massive queues and exceeded the 10-second backend limit.");
      } else {
          setSimError(error.message); 
      }
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900 font-sans">
      <div className="w-80 bg-white border-r border-slate-200 p-6 overflow-y-auto h-screen sticky top-0 shadow-sm z-10 shrink-0 custom-scrollbar">
        <h2 className="text-2xl font-black flex items-center gap-2 mb-8 text-indigo-600 tracking-tight"><Activity size={28} /> Control Panel</h2>
        
        <div className={`mb-6 p-4 rounded-xl border transition-colors duration-300 ${cap.ratio > 100 ? 'bg-red-50 border-red-200' : cap.ratio > 80 ? 'bg-orange-50 border-orange-200' : 'bg-emerald-50 border-emerald-200'}`}>
            <h3 className={`font-black flex items-center gap-2 mb-2 text-sm ${cap.ratio > 100 ? 'text-red-700' : cap.ratio > 80 ? 'text-orange-700' : 'text-emerald-700'}`}>
                <Gauge size={16} /> Intersection Saturation
            </h3>
            <div className="w-full bg-slate-200 rounded-full h-2.5 mb-2 overflow-hidden">
                <div className={`h-2.5 rounded-full transition-all duration-500 ${cap.ratio > 100 ? 'bg-red-500' : cap.ratio > 80 ? 'bg-orange-500' : 'bg-emerald-500'}`} style={{ width: `${Math.min(cap.ratio, 100)}%` }}></div>
            </div>
            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                Demand: {cap.demand.toFixed(1)} / Capacity: {cap.limit.toFixed(1)}
            </p>
            {cap.ratio > 100 && <p className="text-xs text-red-600 font-bold mt-2 animate-pulse">⚠️ Structural Gridlock Imminent</p>}
        </div>

        <div className="space-y-6 text-sm">
          <div><label className="flex items-center justify-between font-bold mb-2 text-slate-700"><span>Cycles</span><span className="bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded text-xs">{totalCycles}</span></label>
            <input type="range" min="10" max="200" value={totalCycles} onChange={(e) => setTotalCycles(Number(e.target.value))} className="w-full accent-indigo-600" /></div>
          <div className="border-t border-slate-100 pt-5"><h3 className="font-bold mb-4 flex items-center gap-2 text-slate-700"><Timer size={16} /> Manual Timings (s)</h3>
            <div className="grid grid-cols-2 gap-3">{['North', 'South', 'East', 'West'].map(lane => (
                <div key={lane} className="flex flex-col"><label className="text-[10px] uppercase font-bold text-slate-400 mb-1">{lane}</label>
                  <input type="number" value={(fxTimes as any)[lane]} onChange={(e) => setFxTimes({...fxTimes, [lane]: Number(e.target.value)})} className="border rounded-md p-1.5 text-center outline-none text-xs font-mono font-bold" /></div>
              ))}</div></div>
          <div className="border-t border-slate-100 pt-5"><h3 className="font-bold mb-4 flex items-center gap-2 text-slate-700"><Car size={16} /> Arrivals / Minute</h3>
            {['North', 'South', 'East', 'West'].map(lane => (
              <div key={lane} className="mb-3 flex items-center justify-between"><label className="block text-[10px] uppercase font-bold text-slate-500 w-12">{lane}</label>
                <div className="flex gap-1"><input type="number" value={(arrivalsPerMin as any)[lane][0]} onChange={(e) => setArrivalsPerMin({...arrivalsPerMin, [lane]: [Number(e.target.value), (arrivalsPerMin as any)[lane][1]]})} className="w-14 border rounded-md p-1.5 text-center outline-none text-xs" />
                  <span className="text-slate-300 self-center">-</span><input type="number" value={(arrivalsPerMin as any)[lane][1]} onChange={(e) => setArrivalsPerMin({...arrivalsPerMin, [lane]: [(arrivalsPerMin as any)[lane][0], Number(e.target.value)]})} className="w-14 border rounded-md p-1.5 text-center outline-none text-xs" /></div></div>
            ))}</div>
          <div className="border-t border-slate-100 pt-5"><label className="flex items-center justify-between font-bold mb-2 text-slate-700"><span>Avg Time / Vehicle</span><span className="bg-slate-100 px-2 py-0.5 rounded text-xs">{avgCarTime}s</span></label>
            <input type="range" min="1" max="4" step="0.5" value={avgCarTime} onChange={(e) => setAvgCarTime(Number(e.target.value))} className="w-full accent-indigo-600" /></div>
          <div className="border-t border-slate-100 pt-5"><h3 className="font-bold mb-4 flex items-center gap-2 text-slate-700"><GitMerge size={16} /> Number of Lanes</h3>
            <div className="grid grid-cols-2 gap-3"><div className="flex flex-col"><label className="text-[10px] uppercase font-bold text-slate-400 mb-1">North/South</label><input type="number" min="1" max="6" value={lanes.NS} onChange={(e) => setLanes({...lanes, NS: Number(e.target.value)})} className="border rounded-md p-1.5 text-center outline-none text-xs font-bold" /></div>
              <div className="flex flex-col"><label className="text-[10px] uppercase font-bold text-slate-400 mb-1">East/West</label><input type="number" min="1" max="6" value={lanes.EW} onChange={(e) => setLanes({...lanes, EW: Number(e.target.value)})} className="border rounded-md p-1.5 text-center outline-none text-xs font-bold" /></div></div></div>
          <div className="border-t border-slate-100 pt-5 pb-2"><div className="bg-red-50 p-4 rounded-xl border border-red-100 shadow-inner"><h3 className="font-black mb-4 flex items-center gap-2 text-red-700 text-sm"><Siren size={18} /> EV Probability (%)</h3>
              {['North', 'South', 'East', 'West'].map(lane => (
                <div key={lane} className="mb-3 last:mb-0"><label className="flex justify-between text-[10px] uppercase font-black text-red-400 mb-1"><span>{lane}</span><span>{(evProbs as any)[lane]}%</span></label>
                  <input type="range" min="0" max="100" value={(evProbs as any)[lane]} onChange={(e) => setEvProbs({...evProbs, [lane]: Number(e.target.value)})} className="w-full accent-red-500" /></div>
              ))}</div></div>
          
          {simError && (
            <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl text-xs font-medium whitespace-pre-line shadow-sm">
              <div className="font-black flex items-center gap-1 mb-2"><AlertTriangle size={14}/> Error</div>
              {simError}
            </div>
          )}

          <button onClick={runSimulation} disabled={isSimulating} className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold hover:bg-slate-800 transition disabled:bg-slate-300 shadow-md flex justify-center items-center gap-2">
            {isSimulating ? <><Activity className="animate-spin" size={16} /> Simulating...</> : "Launch Simulation"}
          </button>
        </div>
      </div>

      <div className="flex-1 p-10 overflow-x-hidden">
        <header className="mb-10 flex justify-between items-start">
          <div><div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-sm font-bold mb-4"><Zap size={14} /> Neural ML Engine</div>
            <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">Smart City Traffic AI</h1>
            <p className="text-slate-500 mt-2 text-lg">Comparing Machine Learning Control against Fixed Manual Timers.</p></div>
          <button onClick={() => setIsDetailedView(!isDetailedView)} className="flex items-center gap-2 bg-white border px-4 py-2 rounded-lg font-bold text-sm shadow-sm hover:bg-slate-50">
            {isDetailedView ? <Columns size={16} /> : <LayoutList size={16} />} {isDetailedView ? "Side-by-Side View" : "Detailed Stacked View"}
          </button>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <MetricCard title="Fixed Inefficiency" value={metrics.fxLoss.toLocaleString()} icon={<AlertTriangle size={20} />} color="text-red-600" bgColor="bg-red-50" />
          <MetricCard title="ML System Inefficiency" value={metrics.aiLoss.toLocaleString()} icon={<Zap size={20} />} color="text-emerald-600" bgColor="bg-emerald-50" subLabel={`Saved ${Math.max(0, metrics.fxLoss - metrics.aiLoss).toLocaleString()} pts`} />
          <MetricCard title="Total Gain" value={`${metrics.gain.toFixed(1)}%`} icon={<TrendingDown size={20} />} color="text-indigo-600" bgColor="bg-indigo-50" />
        </div>

        <div className={`grid gap-8 items-start ${isDetailedView ? 'grid-cols-1' : '2xl:grid-cols-2'}`}>
          <TableSection title="ML Optimized Log" data={aiLogs} detailed={isDetailedView} color="emerald" />
          <TableSection title="Fixed Manual Log" data={fxLogs} detailed={isDetailedView} color="slate" />
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, color, bgColor, icon, subLabel }: any) {
  return (
    <div className={`p-6 rounded-2xl shadow-sm border bg-white flex flex-col transition-all duration-300`}>
      <div className="flex items-center gap-2 text-slate-500 mb-3 font-semibold text-sm uppercase">{React.cloneElement(icon, { className: color })} {title}</div>
      <div className="flex items-end justify-between mt-auto">
        <h3 className={`text-4xl font-black ${color}`}>{value}</h3>
        {subLabel && <span className={`text-xs font-bold ${color} ${bgColor} px-2.5 py-1 rounded-full`}>{subLabel}</span>}
      </div>
    </div>
  );
}

function TableSection({ title, data, detailed, color }: any) {
  if (!data || data.length === 0) return <div className="bg-white border-dashed border-2 rounded-xl h-64 flex items-center justify-center text-slate-400 font-medium">Awaiting simulation...</div>;
  return (
    <section>
      <h2 className={`text-xl font-bold mb-4 flex items-center gap-2 text-${color}-700`}>{title}</h2>
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden relative">
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto custom-scrollbar">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-slate-50 font-semibold text-xs uppercase tracking-wider sticky top-0 z-10 border-b">
              <tr><th className="px-5 py-4">Phase</th><th className="px-5 py-4">Queue</th><th className="px-5 py-4">Timing</th><th className="px-5 py-4 text-right">Loss</th><th className="px-5 py-4">Details</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((row: any, idx: number) => (
                <tr key={idx} className="hover:bg-slate-50 bg-white transition-colors">
                  <td className="px-5 py-3 font-medium"><span className="text-slate-400 text-xs mr-2">C{row?.Cycle}</span>{row?.["Phase Sequence"]}</td>
                  <td className="px-5 py-3 font-medium">{Number(row?.Queue) > 50 ? <span className="text-red-600 animate-pulse">🛑 {row.Queue}</span> : row?.Queue}</td>
                  <td className="px-5 py-3 font-mono text-indigo-600 text-xs bg-indigo-50/50 rounded">{row?.["Allocated ➡️ Used"]}</td>
                  <td className="px-5 py-3 font-bold text-slate-700 text-right">{row?.["Cycle Loss"]}</td>
                  <td className="px-5 py-3 text-xs text-slate-500">
                    <div className="font-medium text-slate-700">{row?.Events}</div>
                    
                    {detailed && (
                      <div className="mt-2 flex flex-col gap-2">
                        <div className="flex flex-wrap gap-2 text-[10px] uppercase font-bold text-slate-500 bg-slate-50 p-2 rounded border">
                          <span className="bg-white px-1.5 py-0.5 rounded border">📥 ARR: {row?.Arrivals ?? 0}</span>
                          <span className={`px-1.5 py-0.5 rounded border ${(row?.Failed || 0) > 0 ? 'bg-red-50 text-red-600 border-red-200' : 'bg-white'}`}>❌ FAIL: {row?.Failed ?? 0}</span>
                          <span className={`px-1.5 py-0.5 rounded border ${row?.RedTime > 60 ? 'bg-orange-50 text-orange-600 border-orange-200' : 'bg-slate-100'}`}>🛑 RED: {row?.RedTime ?? 0}S</span>
                          <span className="bg-sky-50 text-sky-600 px-1.5 py-0.5 rounded border border-sky-200">⏳ WAIT LOSS: {row?.LossWait ?? 0}</span>
                          <span className="bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded border border-indigo-200">💥 FAIL LOSS: {row?.LossFail ?? 0}</span>
                          <span className="bg-rose-50 text-rose-600 px-1.5 py-0.5 rounded border border-rose-200">🚗 QUEUE LOSS: {row?.LossQueue ?? 0}</span>
                          
                          {row?.LossStarve > 0 && (
                            <span className="bg-red-600 text-white px-1.5 py-0.5 rounded shadow-sm animate-pulse">🚨 STARVED: {row?.LossStarve} PTS</span>
                          )}
                        </div>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
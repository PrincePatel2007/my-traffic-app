"use client";
import React, { useState } from 'react';
import { Zap, Play, Activity, AlertTriangle, TrendingDown, Clock, Car, Siren, LayoutList, Columns } from 'lucide-react';

export default function TrafficDashboard() {
  const [totalCycles, setTotalCycles] = useState(50);
  const [avgCarTime, setAvgCarTime] = useState(5);
  const [arrivals, setArrivals] = useState({ North: [2, 12], South: [2, 12], East: [5, 15], West: [5, 15] });
  const [evProbs, setEvProbs] = useState({ North: 5, South: 5, East: 5, West: 5 });
  const [aiLogs, setAiLogs] = useState<any[]>([]);
  const [fxLogs, setFxLogs] = useState<any[]>([]);
  const [metrics, setMetrics] = useState({ aiLoss: 0, fxLoss: 0, gain: 0 });
  const [isSimulating, setIsSimulating] = useState(false);
  const [isDetailedView, setIsDetailedView] = useState(false);

  const runSimulation = async () => {
    setIsSimulating(true); setAiLogs([]); setFxLogs([]);
    try {
      const res = await fetch('/api/simulate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ total_cycles: totalCycles, avg_car_time: avgCarTime, arrival_ranges: arrivals, ev_probs: { North: evProbs.North/100, South: evProbs.South/100, East: evProbs.East/100, West: evProbs.West/100 } })
      });
      const data = await res.json();
      let i = 0;
      const interval = setInterval(() => {
        if (i >= data.ai_logs.length) { clearInterval(interval); setIsSimulating(false); return; }
        setAiLogs(p => [data.ai_logs[i], ...p]); setFxLogs(p => [data.fx_logs[i], ...p]);
        const aiL = data.ai_logs.slice(0, i+1).reduce((a:number, r:any)=> a + r["Cycle Loss"], 0);
        const fxL = data.fx_logs.slice(0, i+1).reduce((a:number, r:any)=> a + r["Cycle Loss"], 0);
        setMetrics({ aiLoss: aiL, fxLoss: fxL, gain: fxL > 0 ? ((fxL-aiL)/fxL)*100 : 0 });
        i++;
      }, 100);
    } catch (e) { setIsSimulating(false); alert("Backend Error"); }
  };

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900 font-sans">
      <div className="w-80 bg-white border-r border-slate-200 p-6 overflow-y-auto h-screen sticky top-0 shadow-sm shrink-0">
        <h2 className="text-2xl font-black flex items-center gap-2 mb-8 text-indigo-600 tracking-tight"><Activity size={28}/> Control Panel</h2>
        <div className="space-y-6 text-sm">
          <div><label className="font-bold flex justify-between">Cycles <span>{totalCycles}</span></label>
          <input type="range" min="10" max="200" value={totalCycles} onChange={e=>setTotalCycles(+e.target.value)} className="w-full accent-indigo-600"/></div>
          <div className="pt-4 border-t"><h3 className="font-bold mb-3 flex items-center gap-2"><Car size={16}/> Arrivals Range</h3>
          {['North','South','East','West'].map(l=>(
            <div key={l} className="flex justify-between items-center mb-2"><span className="text-xs font-bold text-slate-500 uppercase">{l}</span>
            <div className="flex gap-1"><input type="number" value={(arrivals as any)[l][0]} onChange={e=>setArrivals({...arrivals,[l]:[+e.target.value,(arrivals as any)[l][1]]})} className="w-12 border rounded p-1 text-center text-xs"/>
            <input type="number" value={(arrivals as any)[l][1]} onChange={e=>setArrivals({...arrivals,[l]:[(arrivals as any)[l][0],+e.target.value]})} className="w-12 border rounded p-1 text-center text-xs"/></div></div>
          ))}</div>
          <div className="pt-4 border-t"><h3 className="font-bold mb-3 flex items-center gap-2 text-red-500"><Siren size={16}/> EV Probability (%)</h3>
          {['North','South','East','West'].map(l=>(
            <div key={l} className="mb-2"><label className="flex justify-between text-[10px] font-bold uppercase text-slate-400"><span>{l}</span><span>{(evProbs as any)[l]}%</span></label>
            <input type="range" min="0" max="100" value={(evProbs as any)[l]} onChange={e=>setEvProbs({...evProbs,[l]:+e.target.value})} className="w-full accent-red-500"/></div>
          ))}</div>
          <button onClick={runSimulation} disabled={isSimulating} className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold hover:bg-slate-800 disabled:bg-slate-300 mt-4 flex items-center justify-center gap-2 shadow-md">
            {isSimulating ? "Simulating..." : <><Play size={18} fill="currentColor"/> Run Simulation</>}
          </button>
        </div>
      </div>
      <div className="flex-1 p-10">
        <header className="mb-10 flex justify-between items-center">
          <div><h1 className="text-4xl font-black tracking-tight">Smart City Traffic AI</h1><p className="text-slate-500 font-medium">Adaptive AI Control vs Fixed Manual Timers</p></div>
          <button onClick={()=>setIsDetailedView(!isDetailedView)} className="flex items-center gap-2 bg-white border border-slate-200 px-4 py-2 rounded-lg font-bold text-sm shadow-sm hover:bg-slate-50">
            {isDetailedView ? <><Columns size={16} className="text-indigo-600"/> Side View</> : <><LayoutList size={16} className="text-indigo-600"/> Detailed View</>}
          </button>
        </header>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <MetricCard title="Fixed Loss" value={metrics.fxLoss.toLocaleString()} color="text-red-600" bgColor="bg-red-50" icon={<AlertTriangle size={20}/>} />
          <MetricCard title="AI Loss" value={metrics.aiLoss.toLocaleString()} color="text-emerald-600" bgColor="bg-emerald-50" icon={<Zap size={20}/>} subLabel={`Saved ${(metrics.fxLoss-metrics.aiLoss).toLocaleString()} pts`}/>
          <MetricCard title="Efficiency Gain" value={`${metrics.gain.toFixed(1)}%`} color="text-indigo-600" bgColor="bg-indigo-50" icon={<TrendingDown size={20}/>}/>
        </div>
        <div className={`grid gap-8 ${isDetailedView ? 'grid-cols-1' : '2xl:grid-cols-2'}`}>
          <TableSection title="AI Optimized Log" data={aiLogs} detailed={isDetailedView} color="emerald"/>
          <TableSection title="Fixed Manual Log" data={fxLogs} detailed={isDetailedView} color="slate"/>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, color, bgColor, icon, subLabel }: any) {
  return (
    <div className={`p-6 rounded-2xl bg-white border border-slate-100 shadow-sm`}>
      <div className="flex items-center gap-2 text-slate-400 font-bold text-xs uppercase mb-3">{React.cloneElement(icon, {className: color})} {title}</div>
      <div className="flex justify-between items-end"><h3 className={`text-4xl font-black ${color}`}>{value}</h3>{subLabel && <span className={`text-[10px] font-black ${color} ${bgColor} px-2 py-1 rounded-full`}>{subLabel}</span>}</div>
    </div>
  );
}

function TableSection({ title, data, detailed, color }: any) {
  return (
    <section>
      <h2 className={`text-xl font-bold mb-4 flex items-center gap-2 text-${color}-700`}>{title}</h2>
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <table className="w-full text-left text-xs whitespace-nowrap">
            <thead className="bg-slate-50 sticky top-0 font-black text-slate-400 uppercase tracking-tighter border-b">
              <tr><th className="px-4 py-3">Phase</th><th className="px-4 py-3">Queue</th><th className="px-4 py-3">Timing</th><th className="px-4 py-3 text-right">Loss</th><th className="px-4 py-3">Details</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((r:any, i:number) => (
                <tr key={i} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 font-bold text-slate-900"><span className="text-slate-300 mr-1">C{r.Cycle}</span>{r["Phase Sequence"]}</td>
                  <td className="px-4 py-3 font-bold">{r.Queue > 50 ? <span className="text-red-500 animate-pulse">🛑 {r.Queue}</span> : r.Queue}</td>
                  <td className="px-4 py-3 font-mono text-indigo-600 bg-indigo-50/30">{r["Allocated ➡️ Used"]}</td>
                  <td className="px-4 py-3 text-right font-black">{r["Cycle Loss"]}</td>
                  <td className="px-4 py-3">
                    <div className="font-bold text-slate-600">{r.Events}</div>
                    {detailed && (
                      <div className="mt-2 flex gap-1 text-[9px] font-black uppercase">
                        <span className="bg-slate-100 px-1 py-0.5 rounded">📥 ARRIVALS: {r.Arrivals}</span>
                        <span className={`px-1 py-0.5 rounded ${r.Failed > 0 ? 'bg-red-100 text-red-600' : 'bg-slate-100'}`}>❌ FAILED: {r.Failed}</span>
                        <span className="bg-sky-100 text-sky-600 px-1 py-0.5 rounded">⏱️ AVG WAIT: {r.AvgWait}s</span>
                        <span className="bg-indigo-100 text-indigo-600 px-1 py-0.5 rounded">⏳ PENALTY: {r.WaitPenalty}</span>
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
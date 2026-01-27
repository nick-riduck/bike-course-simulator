import React from 'react';
import useCourseStore from '../stores/useCourseStore';

const SegmentList = () => {
  const { 
    segments, riderProfile, updateSegment, selectedSegmentIds, 
    toggleSegmentSelection, mergeSelectedSegments, exportGpx, 
    runSimulation, simulationResult, exportJson 
  } = useCourseStore();

  const formatTime = (seconds) => {
    if (!seconds || seconds <= 0) return "--:--";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  if (!segments || segments.length === 0) {
    return (
      <div className="p-10 text-center text-gray-500 italic bg-[#1E1E1E] rounded-xl border border-gray-800 h-full flex items-center justify-center">
        No segments. Load GPX.
      </div>
    );
  }

  return (
    <div className="bg-[#1E1E1E] rounded-xl border border-gray-800 shadow-lg overflow-hidden flex flex-col h-full">
      <div className="p-4 border-b border-gray-700 bg-gray-800/50 flex justify-between items-center">
        <h2 className="text-lg font-bold text-[#2a9e92]">Course Strategy</h2>
        <div className="flex gap-2">
          {selectedSegmentIds.length > 1 && (
            <button 
              onClick={mergeSelectedSegments}
              className="bg-yellow-600 hover:bg-yellow-500 text-white text-xs px-3 py-1 rounded font-bold transition-colors shadow-sm"
            >
              Merge ({selectedSegmentIds.length})
            </button>
          )}
          <button 
            onClick={exportGpx}
            className="bg-[#2a9e92] hover:bg-[#218c82] text-white text-xs px-3 py-1 rounded font-bold transition-colors shadow-sm"
          >
            Save
          </button>
          <button 
            onClick={runSimulation}
            className="bg-purple-600 hover:bg-purple-500 text-white text-xs px-3 py-1 rounded font-bold transition-colors shadow-sm"
          >
            Simulate
          </button>
        </div>
      </div>
      
      <div className="overflow-y-auto flex-1 custom-scrollbar">
        <table className="w-full text-left border-collapse table-fixed">
          <thead className="sticky top-0 bg-[#1E1E1E] z-10 shadow-sm">
            <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-gray-700">
              <th className="px-2 py-3 font-semibold w-8 text-center">#</th>
              <th className="px-2 py-3 font-semibold text-right w-14">Start</th>
              <th className="px-2 py-3 font-semibold text-right w-14">Dist</th>
              <th className="px-2 py-3 font-semibold text-right w-14">Grade</th>
              <th className="px-2 py-3 font-semibold text-right w-16">Time</th>
              <th className="px-4 py-3 font-semibold text-right">Power(W)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {segments.map((seg, idx) => {
              const isSelected = selectedSegmentIds.includes(seg.id);
              return (
                <tr 
                  key={seg.id} 
                  className={`transition-colors cursor-pointer group ${
                    isSelected 
                      ? 'bg-yellow-500/20 border-l-4 border-yellow-400' 
                      : 'hover:bg-gray-700/30 border-l-4 border-transparent'
                  }`}
                  onClick={(e) => toggleSegmentSelection(seg.id, e.shiftKey)}
                >
                  <td className="px-2 py-3 text-center">
                    <div className={`w-5 h-5 mx-auto flex items-center justify-center rounded text-[10px] font-bold ${
                      seg.type === 'UP' ? 'bg-red-900/60 text-red-300' :
                      seg.type === 'DOWN' ? 'bg-cyan-900/60 text-cyan-300' :
                      'bg-green-900/60 text-green-300'
                    }`}>
                      {idx + 1}
                    </div>
                  </td>
                  <td className="px-2 py-3 text-xs text-right text-gray-400 font-mono">
                    {(seg.start_dist / 1000).toFixed(1)}
                  </td>
                  <td className="px-2 py-3 text-xs text-right text-gray-300 font-mono">
                    {((seg.end_dist - seg.start_dist) / 1000).toFixed(1)}
                  </td>
                  <td className={`px-2 py-3 text-xs text-right font-mono font-bold ${seg.avg_grade > 0 ? 'text-red-400' : 'text-cyan-400'}`}>
                    {seg.avg_grade?.toFixed(1)}%
                  </td>
                  <td className="px-2 py-3 text-xs text-right text-purple-400 font-mono font-bold">
                    {seg.simulated_duration ? formatTime(seg.simulated_duration) : '--'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-gray-300">
                    {seg.simulated_avg_power ? Math.round(seg.simulated_avg_power) : '--'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="p-4 bg-gray-800/30 border-t border-gray-700">
        <div className="flex justify-between text-xs mb-2">
          <span className="text-gray-400 font-medium">TOTAL COURSE</span>
          <span className="font-bold text-white">
            {(segments[segments.length - 1].end_dist / 1000).toFixed(2)} km
          </span>
        </div>
        
        {simulationResult && (
          <div className="mt-2 pt-2 border-t border-gray-700 grid grid-cols-2 gap-2">
            <div className="bg-gray-900 p-2 rounded shadow-inner">
              <div className="text-[10px] text-gray-500 uppercase font-bold">Est. Time</div>
              <div className="text-lg font-bold text-purple-400 font-mono">{formatTime(simulationResult.total_time_sec)}</div>
            </div>
            <div className="bg-gray-900 p-2 rounded shadow-inner">
              <div className="text-[10px] text-gray-500 uppercase font-bold">Avg Speed</div>
              <div className="text-lg font-bold text-purple-400 font-mono">{simulationResult.avg_speed_kmh?.toFixed(1)} <span className="text-[10px]">km/h</span></div>
            </div>
            <div className="bg-gray-900 p-2 rounded">
              <div className="text-[10px] text-gray-500 uppercase">Avg Power</div>
              <div className="text-sm font-bold text-gray-300">{Math.round(simulationResult.avg_power || 0)}W</div>
            </div>
            <div className="bg-gray-900 p-2 rounded">
              <div className="text-[10px] text-gray-500 uppercase">NP / Work</div>
              <div className="text-sm font-bold text-gray-300">
                {Math.round(simulationResult.normalized_power || 0)}W <span className="text-gray-500">/</span> {Math.round(simulationResult.work_kj || 0)}kJ
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SegmentList;
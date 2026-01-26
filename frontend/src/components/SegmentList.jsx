import React from 'react';
import useCourseStore from '../stores/useCourseStore';

const SegmentList = () => {
  const { segments, riderProfile, updateSegment, selectedSegmentIds, toggleSegmentSelection, mergeSelectedSegments } = useCourseStore();

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
          <span className="text-xs text-gray-400 self-center">{segments.length} Segs</span>
          {selectedSegmentIds.length > 1 && (
            <button 
              onClick={mergeSelectedSegments}
              className="bg-yellow-600 hover:bg-yellow-500 text-white text-xs px-3 py-1 rounded font-bold transition-colors shadow-sm"
            >
              Merge ({selectedSegmentIds.length})
            </button>
          )}
        </div>
      </div>
      
      <div className="overflow-y-auto flex-1 custom-scrollbar">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-[#1E1E1E] z-10 shadow-sm">
            <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-gray-700">
              <th className="px-4 py-3 font-semibold w-10">NO</th>
              <th className="px-2 py-3 font-semibold text-center">Type</th>
              <th className="px-2 py-3 font-semibold text-right">Start</th>
              <th className="px-2 py-3 font-semibold text-right">Dist</th>
              <th className="px-4 py-3 font-semibold text-right w-24">Power(W)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {segments.map((seg, idx) => {
              const isSelected = selectedSegmentIds.includes(seg.id);
              return (
                <tr 
                  key={seg.id} 
                  className={`transition-colors cursor-pointer ${
                    isSelected 
                      ? 'bg-yellow-500/20 border-l-4 border-yellow-400' 
                      : 'hover:bg-gray-700/30 border-l-4 border-transparent'
                  }`}
                  onClick={(e) => toggleSegmentSelection(seg.id, e.shiftKey)}
                >
                  <td className="px-4 py-3 text-sm font-medium text-gray-400 font-mono">
                    {idx + 1}
                  </td>
                  <td className="px-2 py-3 text-center">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                      seg.type === 'UP' ? 'bg-red-900/40 text-red-400' :
                      seg.type === 'DOWN' ? 'bg-cyan-900/40 text-cyan-400' :
                      'bg-green-900/40 text-green-400'
                    }`}>
                      {seg.type}
                    </span>
                  </td>
                  <td className="px-2 py-3 text-xs text-right text-gray-400 font-mono">
                    {(seg.start_dist / 1000).toFixed(1)}
                  </td>
                  <td className="px-2 py-3 text-xs text-right text-gray-400 font-mono">
                    {((seg.end_dist - seg.start_dist) / 1000).toFixed(1)}
                  </td>
                  <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                    <input 
                      type="number"
                      className="w-16 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-right text-[#2a9e92] focus:border-[#2a9e92] focus:outline-none transition-all"
                      value={Math.round(seg.target_power)}
                      onChange={(e) => updateSegment(seg.id, { target_power: Number(e.target.value) })}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="p-4 bg-gray-800/30 border-t border-gray-700">
        <div className="flex justify-between text-xs mb-2">
          <span className="text-gray-400">Total Distance</span>
          <span className="font-bold text-white">
            {(segments[segments.length - 1].end_dist / 1000).toFixed(2)}km
          </span>
        </div>
      </div>
    </div>
  );
};

export default SegmentList;
import React from 'react';
import useCourseStore from '../stores/useCourseStore';

const SegmentList = () => {
  const { segments, riderProfile, updateSegment } = useCourseStore();

  if (segments.length === 0) {
    return (
      <div className="p-10 text-center text-gray-500 italic bg-riduck-card rounded-xl border border-gray-800">
        No segments detected. Load a GPX file first.
      </div>
    );
  }

  return (
    <div className="bg-riduck-card rounded-xl border border-gray-800 shadow-lg overflow-hidden flex flex-col h-full">
      <div className="p-4 border-b border-gray-700 bg-gray-800/50 flex justify-between items-center">
        <h2 className="text-lg font-bold text-riduck-primary">Course Strategy</h2>
        <span className="text-xs text-gray-400">{segments.length} Segments</span>
      </div>
      
      <div className="overflow-y-auto flex-1 custom-scrollbar">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-riduck-card z-10 shadow-sm">
            <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-gray-700">
              <th className="px-4 py-3 font-semibold">Name</th>
              <th className="px-2 py-3 font-semibold text-center">Type</th>
              <th className="px-2 py-3 font-semibold text-right">Dist</th>
              <th className="px-4 py-3 font-semibold text-right w-24">Power(W)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {segments.map((seg) => (
              <tr key={seg.id} className="hover:bg-gray-700/30 transition-colors group">
                <td className="px-4 py-3 text-sm font-medium text-gray-200">
                  {seg.name}
                </td>
                <td className="px-2 py-3 text-center">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                    seg.type === 'UP' ? 'bg-riduck-uphill/20 text-riduck-uphill' :
                    seg.type === 'DOWN' ? 'bg-riduck-downhill/20 text-riduck-downhill' :
                    'bg-riduck-flat/20 text-riduck-flat'
                  }`}>
                    {seg.type}
                  </span>
                </td>
                <td className="px-2 py-3 text-xs text-right text-gray-400 font-mono">
                  {((seg.end_dist - seg.start_dist) / 1000).toFixed(1)}km
                </td>
                <td className="px-4 py-3 text-right">
                  <input 
                    type="number"
                    className="w-16 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-right text-riduck-primary focus:border-riduck-primary focus:outline-none transition-all"
                    value={Math.round(seg.target_power)}
                    onChange={(e) => {/* TODO: Update Store */}}
                  />
                </td>
              </tr>
            ))}
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
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">Estimated NP</span>
          <span className="font-bold text-riduck-primary">--- W</span>
        </div>
      </div>
    </div>
  );
};

export default SegmentList;

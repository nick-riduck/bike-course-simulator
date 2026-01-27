import React, { useState } from 'react';
import useCourseStore from '../stores/useCourseStore';

const RiderSettings = () => {
  const { riderProfile, updateRiderProfile, riderPresets, applyRiderPreset, updatePdcValue, deletePdcValue } = useCourseStore();
  const [isOpen, setIsOpen] = useState(false);
  
  // Local state for adding new PDC values
  const [newDuration, setNewDuration] = useState('');
  const [newPower, setNewPower] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    updateRiderProfile({ [name]: parseFloat(value) });
  };

  const handlePresetChange = (e) => {
    applyRiderPreset(e.target.value);
  };

  const handlePdcChange = (duration, val) => {
      updatePdcValue(duration, parseFloat(val));
  };

  const handleAddPdc = () => {
      if (newDuration && newPower) {
          updatePdcValue(newDuration, parseFloat(newPower));
          setNewDuration('');
          setNewPower('');
      }
  };

  // Sort PDC keys for display
  const sortedPdcKeys = Object.keys(riderProfile.pdc || {}).sort((a,b) => parseInt(a) - parseInt(b));

  return (
    <div className="bg-[#1E1E1E] rounded-xl border border-gray-800 shadow-lg p-4 mb-6">
      <div className="flex justify-between items-center cursor-pointer" onClick={() => setIsOpen(!isOpen)}>
        <div className="flex flex-col">
            <h3 className="text-sm font-bold text-[#2a9e92] uppercase tracking-wider flex items-center gap-2">
            Rider Profile
            <span className="text-[10px] bg-gray-800 px-2 py-0.5 rounded-full text-gray-400 font-normal normal-case ml-2">
                {riderProfile.name || 'Custom Rider'} | CP: {riderProfile.cp}W
            </span>
            </h3>
        </div>
        <span className="text-gray-500 text-xs">{isOpen ? 'COLLAPSE ▲' : 'EDIT PROFILE ▼'}</span>
      </div>

      {isOpen && (
        <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="md:col-span-4 bg-gray-900/50 p-3 rounded border border-gray-800 mb-2">
            <label className="block text-[10px] text-gray-500 uppercase font-bold mb-2">Load Preset From JSON</label>
            <select 
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-xs text-white outline-none focus:border-[#2a9e92]"
                onChange={handlePresetChange}
                defaultValue="rider_a"
            >
                {Object.entries(riderPresets).map(([key, r]) => (
                    <option key={key} value={key}>{r.name}</option>
                ))}
            </select>
            {riderProfile.note && (
                <p className="text-[10px] text-gray-400 mt-2 italic">Note: {riderProfile.note}</p>
            )}
          </div>

          <div>
            <label className="block text-gray-500 text-[10px] uppercase font-bold mb-1">Weight (kg)</label>
            <input
              type="number" name="weight_kg"
              value={riderProfile.weight_kg}
              onChange={handleChange}
              className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-white focus:border-[#2a9e92] outline-none text-xs"
            />
          </div>
          <div>
            <label className="block text-gray-500 text-[10px] uppercase font-bold mb-1">CP (Watts)</label>
            <input
              type="number" name="cp"
              value={riderProfile.cp}
              onChange={handleChange}
              className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-white focus:border-[#2a9e92] outline-none text-xs"
            />
          </div>
          <div>
            <label className="block text-gray-500 text-[10px] uppercase font-bold mb-1">W' (Joules)</label>
            <input
              type="number" name="w_prime"
              value={riderProfile.w_prime}
              onChange={handleChange}
              className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-white focus:border-[#2a9e92] outline-none text-xs"
            />
          </div>
          <div>
            <label className="block text-gray-500 text-[10px] uppercase font-bold mb-1">Bike Weight (kg)</label>
            <input
              type="number" name="bike_weight"
              value={riderProfile.bike_weight}
              onChange={handleChange}
              className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-white focus:border-[#2a9e92] outline-none text-xs"
            />
          </div>
          
          <div className="md:col-span-4 mt-2 pt-2 border-t border-gray-800">
            <label className="block text-gray-500 text-[10px] uppercase font-bold mb-2">Power Duration Curve (Editable)</label>
            
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2">
                {sortedPdcKeys.map((sec) => (
                    <div key={sec} className="bg-gray-900/50 p-2 rounded border border-gray-800 flex flex-col relative group">
                        <button 
                            onClick={() => deletePdcValue(sec)}
                            className="absolute top-1 right-1 text-gray-600 hover:text-red-500 text-[10px] hidden group-hover:block"
                            title="Remove"
                        >
                            ✕
                        </button>
                        <span className="text-[9px] text-gray-500 mb-1">{parseInt(sec) >= 60 ? `${(parseInt(sec)/60).toFixed(1).replace('.0','')}m (${sec}s)` : `${sec}s`}</span>
                        <div className="flex items-center gap-1">
                            <input 
                                type="number" 
                                value={riderProfile.pdc[sec]}
                                onChange={(e) => handlePdcChange(sec, e.target.value)}
                                className="w-full bg-transparent border-b border-gray-600 focus:border-[#2a9e92] text-xs text-white outline-none font-bold text-center"
                            />
                            <span className="text-[9px] text-gray-600">W</span>
                        </div>
                    </div>
                ))}
                
                {/* Add New PDC Entry */}
                <div className="bg-gray-800/30 p-2 rounded border border-dashed border-gray-700 flex flex-col justify-center items-center gap-1">
                    <div className="flex gap-1 w-full">
                        <input 
                            type="number" placeholder="Sec" 
                            value={newDuration}
                            onChange={e => setNewDuration(e.target.value)}
                            className="w-1/2 bg-gray-900 rounded px-1 py-0.5 text-[10px] text-white outline-none border border-gray-700 focus:border-[#2a9e92]"
                        />
                        <input 
                            type="number" placeholder="Watt" 
                            value={newPower}
                            onChange={e => setNewPower(e.target.value)}
                            className="w-1/2 bg-gray-900 rounded px-1 py-0.5 text-[10px] text-white outline-none border border-gray-700 focus:border-[#2a9e92]"
                        />
                    </div>
                    <button 
                        onClick={handleAddPdc}
                        disabled={!newDuration || !newPower}
                        className="w-full bg-[#2a9e92] hover:bg-[#218c82] disabled:opacity-50 text-white text-[10px] font-bold rounded py-0.5 transition-colors"
                    >
                        + ADD
                    </button>
                </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RiderSettings;

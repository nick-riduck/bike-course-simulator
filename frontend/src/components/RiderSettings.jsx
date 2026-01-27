import React, { useState } from 'react';
import useCourseStore from '../stores/useCourseStore';

const RiderSettings = () => {
  const { riderProfile, updateRiderProfile, riderPresets, applyRiderPreset } = useCourseStore();
  const [isOpen, setIsOpen] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    updateRiderProfile({ [name]: parseFloat(value) });
  };

  const handlePresetChange = (e) => {
    applyRiderPreset(e.target.value);
  };

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
            <label className="block text-gray-500 text-[10px] uppercase font-bold mb-2">Power Duration Curve (PDC)</label>
            <div className="grid grid-cols-3 sm:grid-cols-6 lg:grid-cols-11 gap-2">
                {Object.entries(riderProfile.pdc || {}).sort((a,b) => parseInt(a[0]) - parseInt(b[0])).map(([sec, watt]) => (
                    <div key={sec} className="bg-gray-900/50 p-2 rounded border border-gray-800 flex flex-col items-center">
                        <span className="text-[9px] text-gray-500">{parseInt(sec) >= 60 ? `${parseInt(sec)/60}m` : `${sec}s`}</span>
                        <span className="text-gray-300 font-bold text-xs">{watt}W</span>
                    </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RiderSettings;

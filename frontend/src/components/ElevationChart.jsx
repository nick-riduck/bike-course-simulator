import React, { useMemo } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import useCourseStore from '../stores/useCourseStore';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#1E1E1E] border border-gray-600 p-2 rounded shadow-lg text-xs">
        <p className="font-bold text-white">Dist: {label}km</p>
        <p className="text-[#2a9e92]">Ele: {payload[0].value}m</p>
        <p className="text-gray-400">Grade: {payload[0].payload.grade}%</p>
      </div>
    );
  }
  return null;
};

const ElevationChart = () => {
  const { gpxData, setHoveredDist } = useCourseStore();

  const chartData = useMemo(() => {
    if (!gpxData || gpxData.length === 0) return [];
    
    // Sample data for performance
    const maxPoints = 300;
    const step = Math.max(1, Math.floor(gpxData.length / maxPoints));
    
    return gpxData
      .filter((_, i) => i % step === 0 || i === gpxData.length - 1)
      .map(p => ({
        dist_km: (p.dist_m / 1000).toFixed(2),
        ele: Math.round(p.ele),
        grade: p.grade_pct.toFixed(1),
        original_dist_m: p.dist_m 
      }));
  }, [gpxData]);

  // Manual mouse handler on container to guarantee event firing
  const handleContainerMouseMove = (e) => {
    if (!chartData || chartData.length === 0) return;
    
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const width = 800; // Fixed chart width
    
    // Calculate index from x position
    if (x >= 0 && x <= width) {
      const index = Math.floor((x / width) * chartData.length);
      const point = chartData[Math.min(index, chartData.length - 1)];
      
      if (point) {
        console.log("Chart Hover (Manual):", point.original_dist_m);
        setHoveredDist(point.original_dist_m);
      }
    }
  };

  const handleMouseLeave = () => {
    setHoveredDist(null);
  };

  if (!gpxData || gpxData.length === 0) {
    return (
      <div className="w-full h-48 bg-[#1E1E1E] rounded-xl border border-gray-800 flex items-center justify-center text-gray-500 italic mt-6">
        Load a GPX file to see elevation profile
      </div>
    );
  }

  return (
    <div className="w-full bg-[#1E1E1E] rounded-xl border border-gray-800 p-4 mt-6 shadow-lg">
      <h3 className="text-sm font-bold text-[#2a9e92] mb-2 uppercase tracking-wider">Elevation Profile (km)</h3>
      {/* Container with manual event listener */}
      <div 
        style={{ width: '100%', overflowX: 'auto', cursor: 'crosshair' }}
        onMouseMove={handleContainerMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <AreaChart 
          width={800}
          height={250}
          data={chartData} 
          margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorEle" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#2a9e92" stopOpacity={0.4}/>
              <stop offset="95%" stopColor="#2a9e92" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
          <XAxis dataKey="dist_km" tick={{fontSize: 10, fill: '#666'}} axisLine={false} tickLine={false} />
          <YAxis tick={{fontSize: 10, fill: '#666'}} axisLine={false} tickLine={false} domain={['dataMin - 10', 'dataMax + 10']} />
          <Tooltip content={<CustomTooltip />} />
          <Area type="monotone" dataKey="ele" stroke="#2a9e92" fillOpacity={1} fill="url(#colorEle)" isAnimationActive={false} />
        </AreaChart>
      </div>
    </div>
  );
};

export default ElevationChart;

import React, { useMemo, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import useCourseStore from '../stores/useCourseStore';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const PowerSpeedChart = () => {
  const { simulationResult, hoveredDist, setHoveredDist } = useCourseStore();
  const chartRef = useRef(null);

  // Time-based Moving Average Helper
  const calculateRollingAvg = (trackData, key, windowSec = 30) => {
    if (!trackData) return [];
    
    return trackData.map((point, idx) => {
        const currentTime = point.time_sec;
        const cutoffTime = currentTime - windowSec;
        
        let sum = 0;
        let count = 0;
        
        // Look backwards from current point
        for (let i = idx; i >= 0; i--) {
            if (trackData[i].time_sec < cutoffTime) break;
            sum += trackData[i][key];
            count++;
        }
        
        return count > 0 ? sum / count : 0;
    });
  };

  const chartData = useMemo(() => {
    if (!simulationResult || !simulationResult.track_data) return { datasets: [] };
    
    const track = simulationResult.track_data;
    const labels = track.map(p => (p.dist_km).toFixed(1));

    // Apply 30s Moving Average
    const smoothedPower = calculateRollingAvg(track, 'power', 30);
    const smoothedSpeed = calculateRollingAvg(track, 'speed_kmh', 30);
    
    return {
      labels,
      datasets: [
        {
          label: 'Power (30s Avg)',
          data: smoothedPower,
          borderColor: 'rgba(255, 99, 132, 1)', // Solid Red
          backgroundColor: 'rgba(255, 99, 132, 0.1)',
          borderWidth: 2,
          pointRadius: 0,
          yAxisID: 'y_power',
          tension: 0.3 // Smooth curves
        },
        {
          label: 'Speed (30s Avg)',
          data: smoothedSpeed,
          borderColor: 'rgba(54, 162, 235, 1)', // Solid Blue
          backgroundColor: 'rgba(54, 162, 235, 0.1)',
          borderWidth: 2,
          pointRadius: 0,
          yAxisID: 'y_speed',
          tension: 0.3
        },
        {
          label: 'Elevation',
          data: track.map(p => p.ele),
          borderColor: 'rgba(0, 0, 0, 0)', // Transparent border
          backgroundColor: 'rgba(255, 255, 255, 0.05)', // Very subtle fill
          fill: true,
          pointRadius: 0,
          yAxisID: 'y_ele',
          order: 99 // Background
        }
      ]
    };
  }, [simulationResult]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'top',
        labels: { color: '#aaa', font: { size: 11 } }
      },
      tooltip: {
        backgroundColor: 'rgba(20, 20, 20, 0.95)',
        titleColor: '#fff',
        bodyColor: '#ddd',
        callbacks: {
            title: (items) => `Distance: ${items[0].label} km`,
            label: (ctx) => {
                const label = ctx.dataset.label || '';
                const value = ctx.parsed.y;
                if (label.includes('Power')) return `${label}: ${Math.round(value)} W`;
                if (label.includes('Speed')) return `${label}: ${value.toFixed(1)} km/h`;
                return `${label}: ${Math.round(value)} m`;
            }
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#666', maxTicksLimit: 12 }
      },
      y_power: {
        type: 'linear',
        display: true,
        position: 'left',
        min: 0,
        // Suggested max to keep lines distinct
        suggestedMax: 500, 
        title: { display: true, text: 'Power (W)', color: 'rgba(255, 99, 132, 0.8)', font: {size: 10} },
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#888' }
      },
      y_speed: {
        type: 'linear',
        display: true,
        position: 'right',
        min: 0,
        title: { display: true, text: 'Speed (km/h)', color: 'rgba(54, 162, 235, 0.8)', font: {size: 10} },
        grid: { display: false },
        ticks: { color: '#888' }
      },
      y_ele: {
        type: 'linear',
        display: false, // Purely for background visual
        min: 0
      }
    },
    onHover: (event, activeElements) => {
        if (activeElements.length > 0 && simulationResult?.track_data) {
            const idx = activeElements[0].index;
            const distM = simulationResult.track_data[idx].dist_km * 1000;
            if (Math.abs(distM - hoveredDist) > 50) setHoveredDist(distM);
        }
    }
  }), [simulationResult, hoveredDist, setHoveredDist]);

  if (!simulationResult) return null;

  return (
    <div className="w-full bg-[#1E1E1E] rounded-xl border border-gray-800 p-4 mt-6 shadow-lg h-[320px]">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-sm font-bold text-[#2a9e92] uppercase tracking-wider">Analysis (30s Avg)</h3>
      </div>
      <div className="w-full h-[250px]">
        <Line ref={chartRef} data={chartData} options={options} />
      </div>
    </div>
  );
};

export default PowerSpeedChart;
import React, { useMemo, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend,
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';
import { Line } from 'react-chartjs-2';
import useCourseStore from '../stores/useCourseStore';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend,
  annotationPlugin
);

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
  const { gpxData, hoveredDist, setHoveredDist, segments } = useCourseStore();
  const chartRef = useRef(null);

  // Prepare chart data from GPX
  const chartData = useMemo(() => {
    if (!gpxData || gpxData.length === 0) return { labels: [], datasets: [] };
    
    const labels = gpxData.map(p => (p.dist_m / 1000).toFixed(2));
    const elevations = gpxData.map(p => p.ele);
    
    return {
      labels,
      datasets: [
        {
          fill: true,
          label: 'Elevation (m)',
          data: elevations,
          borderColor: '#2a9e92',
          backgroundColor: 'rgba(42, 158, 146, 0.2)',
          tension: 0.4,
          pointRadius: 0, 
          pointHoverRadius: 5,
          borderWidth: 2,
        },
      ],
    };
  }, [gpxData]);

  // Generate dynamic annotations for segment boundaries and background colors
  const annotations = useMemo(() => {
    if (!segments || segments.length === 0) return {};
    
    const elements = {};
    segments.forEach((seg, i) => {
      const xStart = (seg.start_dist / 1000).toFixed(2);
      const xEnd = (seg.end_dist / 1000).toFixed(2);
      
      // 1. Background Box
      elements[`box${i}`] = {
        type: 'box',
        xMin: xStart,
        xMax: xEnd,
        backgroundColor: seg.type === 'UP' 
          ? 'rgba(244, 67, 54, 0.15)' 
          : (seg.type === 'DOWN' ? 'rgba(0, 172, 193, 0.15)' : 'transparent'),
        borderWidth: 0,
      };

      // 2. Divider Line (only at the end of each segment except the last one)
      if (i < segments.length - 1) {
        elements[`line${i}`] = {
          type: 'line',
          xMin: xEnd,
          xMax: xEnd,
          borderColor: 'rgba(255, 255, 255, 0.2)',
          borderWidth: 1,
          borderDash: [4, 4],
        };
      }
    });
    return elements;
  }, [segments]);

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { display: false },
      annotation: {
        annotations
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: '#1E1E1E',
        titleColor: '#fff',
        bodyColor: '#2a9e92',
        borderColor: '#444',
        borderWidth: 1,
        callbacks: {
          label: (context) => `Ele: ${context.parsed.y}m`,
          title: (items) => `Dist: ${items[0].label}km`,
        }
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#666', maxRotation: 0, autoSkip: true, maxTicksLimit: 10 },
      },
      y: {
        grid: { color: '#333' },
        ticks: { color: '#666' },
        beginAtZero: false,
      },
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false,
    },
    onHover: (event, activeElements) => {
      if (activeElements.length > 0) {
        const index = activeElements[0].index;
        const dist = gpxData[index].dist_m;
        if (dist !== hoveredDist) {
          setHoveredDist(dist);
        }
      } else {
        if (hoveredDist !== null) {
          setHoveredDist(null);
        }
      }
    },
  };

  if (!gpxData || gpxData.length === 0) {
    return (
      <div className="w-full h-48 bg-[#1E1E1E] rounded-xl border border-gray-800 flex items-center justify-center text-gray-500 italic mt-6">
        Load a GPX file to see elevation profile
      </div>
    );
  }

  return (
    <div className="w-full bg-[#1E1E1E] rounded-xl border border-gray-800 p-4 mt-6 shadow-lg h-[300px]">
      <h3 className="text-sm font-bold text-[#2a9e92] mb-2 uppercase tracking-wider">Elevation Profile</h3>
      <div className="w-full h-[230px]">
        <Line ref={chartRef} data={chartData} options={options} />
      </div>
    </div>
  );
};

export default ElevationChart;
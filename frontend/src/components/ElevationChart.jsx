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

  // 1. Prepare chart data from GPX (Linear Scale)
  const data = useMemo(() => {
    if (!gpxData || gpxData.length === 0) return { datasets: [] };
    
    const points = gpxData.map(p => ({
      x: parseFloat((p.dist_m / 1000).toFixed(3)),
      y: Math.round(p.ele),
      original_dist_m: p.dist_m,
      grade: p.grade_pct.toFixed(1)
    }));
    
    return {
      datasets: [
        {
          fill: true,
          label: 'Elevation',
          data: points,
          borderColor: '#2a9e92',
          backgroundColor: 'rgba(42, 158, 146, 0.2)',
          tension: 0.1,
          pointRadius: 0, 
          pointHoverRadius: 5,
          borderWidth: 2,
        },
      ],
    };
  }, [gpxData]);

  // 2. Generate Segment Annotations (Boxes)
  const annotations = useMemo(() => {
    if (!segments || segments.length === 0) return {};
    
    const boxes = {};
    segments.forEach((seg, i) => {
      boxes[`box${i}`] = {
        type: 'box',
        xMin: seg.start_dist / 1000,
        xMax: seg.end_dist / 1000,
        backgroundColor: seg.type === 'UP' 
          ? 'rgba(244, 67, 54, 0.25)' 
          : (seg.type === 'DOWN' ? 'rgba(0, 172, 193, 0.25)' : 'transparent'),
        borderWidth: 0,
        label: {
          display: false
        }
      };
    });
    return boxes;
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
          title: (items) => `Dist: ${items[0].parsed.x}km`,
        }
      },
    },
    scales: {
      x: {
        type: 'linear',
        grid: { display: false },
        ticks: { 
          color: '#666', 
          maxRotation: 0, 
          autoSkip: true,
          callback: (value) => `${value}km` 
        },
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
        const datasetIndex = activeElements[0].datasetIndex;
        const index = activeElements[0].index;
        const point = data.datasets[datasetIndex].data[index];
        if (point && point.original_dist_m !== undefined) {
          if (point.original_dist_m !== hoveredDist) {
            setHoveredDist(point.original_dist_m);
          }
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
        <Line ref={chartRef} data={data} options={options} />
      </div>
    </div>
  );
};

export default ElevationChart;

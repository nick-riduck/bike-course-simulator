import React, { useMemo, useRef, useState } from 'react';
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

const ElevationChart = () => {
  const { 
    gpxData, hoveredDist, setHoveredDist, 
    segments, selectedSegmentIds, toggleSegmentSelection, 
    splitSegment, moveSegmentBoundary, simulationResult 
  } = useCourseStore();
  
  const chartRef = useRef(null);
  const [dragState, setDragState] = useState(null);
  const [mouseDownPos, setMouseDownPos] = useState(null);

  const formatTime = (seconds) => {
    if (!seconds) return "00:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // 1. Chart Data
  const chartData = useMemo(() => {
    if (!gpxData || gpxData.length === 0) return { datasets: [] };
    const points = gpxData.map(p => ({
      x: parseFloat((p.dist_m / 1000).toFixed(3)),
      y: Math.round(p.ele),
      original_dist_m: p.dist_m,
      grade: (p.grade_pct || 0).toFixed(1)
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
          pointHoverRadius: 0,
          borderWidth: 2,
        }
      ],
    };
  }, [gpxData]);

  // 2. Annotations (DEFINED BEFORE OPTIONS)
  const annotations = useMemo(() => {
    if (!segments || segments.length === 0) return {};
    const elements = {};
    segments.forEach((seg, i) => {
      const isSelected = selectedSegmentIds.includes(seg.id);
      
      let effectiveStart = seg.start_dist;
      let effectiveEnd = seg.end_dist;

      if (dragState && dragState.index === i) {
          effectiveEnd = dragState.currentDistM;
      } else if (dragState && dragState.index === i - 1) {
          effectiveStart = dragState.currentDistM;
      }

      elements[`box${i}`] = {
        type: 'box',
        xMin: effectiveStart / 1000,
        xMax: effectiveEnd / 1000,
        backgroundColor: seg.type === 'UP' 
          ? `rgba(244, 67, 54, ${isSelected ? 0.4 : 0.2})` 
          : (seg.type === 'DOWN' ? `rgba(0, 172, 193, ${isSelected ? 0.4 : 0.2})` : `rgba(255, 255, 255, ${isSelected ? 0.2 : 0})`),
        borderWidth: 0,
      };

      if (i < segments.length - 1) {
        const isDraggingThis = dragState && dragState.index === i;
        const linePos = isDraggingThis ? dragState.currentDistM : seg.end_dist;
        elements[`line${i}`] = {
          type: 'line',
          scaleID: 'x',
          value: linePos / 1000,
          borderColor: isDraggingThis ? '#FFD700' : 'rgba(255, 255, 255, 0.5)',
          borderWidth: isDraggingThis ? 3 : 1,
          borderDash: isDraggingThis ? [] : [4, 4],
          enter: (ctx) => !dragState && (ctx.chart.canvas.style.cursor = 'col-resize'),
          leave: (ctx) => !dragState && (ctx.chart.canvas.style.cursor = 'default')
        };
      }
    });
    return elements;
  }, [segments, selectedSegmentIds, dragState]);

  // 3. Options (Uses annotations)
  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { display: false },
      annotation: { annotations },
      tooltip: {
        enabled: true,
        mode: 'index',
        intersect: false,
        backgroundColor: 'rgba(30, 30, 30, 0.9)',
        callbacks: {
          title: (items) => `Dist: ${items[0].parsed.x} km`,
          label: (ctx) => {
            const lines = [`Ele: ${ctx.parsed.y} m`];
            const pt = ctx.dataset.data[ctx.dataIndex];
            if (pt && pt.grade) lines.push(`Grade: ${pt.grade}%`);
            
            // Match simulation data using dist_km
            if (simulationResult && simulationResult.track_data) {
                const distM = pt.original_dist_m || (ctx.parsed.x * 1000);
                // track_data uses dist_km, so compare with distM/1000
                const trackPt = simulationResult.track_data.find(p => Math.abs((p.dist_km * 1000) - distM) < 50); 
                if (trackPt) {
                    lines.push(`Speed: ${trackPt.speed_kmh.toFixed(1)} km/h`);
                    lines.push(`Power: ${Math.round(trackPt.power)} W`);
                    lines.push(`Time: ${formatTime(trackPt.time_sec)}`);
                }
            }
            return lines;
          }
        }
      },
    },
    scales: {
      x: {
        type: 'linear',
        grid: { display: false },
        ticks: { color: '#666', callback: (v) => `${v}km` },
        min: 0,
        max: gpxData.length > 0 ? parseFloat((gpxData[gpxData.length-1].dist_m / 1000).toFixed(3)) : undefined
      },
      y: { grid: { color: '#333' }, ticks: { color: '#666' } }
    },
    interaction: { mode: 'nearest', axis: 'x', intersect: false },
    onHover: (event, activeElements) => {
        if (dragState) return;
        if (activeElements.length > 0) {
            const idx = activeElements[0].index;
            const dsIdx = activeElements[0].datasetIndex;
            // Access point safely
            // Note: chartData is dependency of this useMemo now? No, useMemo deps are [annotations, simulationResult, dragState]
            // We need to access chartData inside here. But chartData is defined in outer scope.
            // So we must include chartData in dependency array.
            // Or better: attach this handler to the Line component prop directly, not inside options useMemo
        }
    }
  }), [annotations, simulationResult, dragState]); // chartData needs to be here if used

  // --- Manual Handlers ---
  const handleMouseDown = (e) => {
    const chart = chartRef.current;
    if (!chart) return;
    const rect = chart.canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    setMouseDownPos({ x: e.clientX, y: e.clientY });
    
    let foundIdx = -1;
    let minDiff = Infinity;
    const HIT_TOLERANCE_PX = 15;

    for (let i = 0; i < segments.length - 1; i++) {
        const seg = segments[i];
        const segEndKm = seg.end_dist / 1000;
        const pixelX = chart.scales.x.getPixelForValue(segEndKm);
        if (Math.abs(mouseX - pixelX) < HIT_TOLERANCE_PX && Math.abs(mouseX - pixelX) < minDiff) {
            minDiff = Math.abs(mouseX - pixelX);
            foundIdx = i;
        }
    }
    if (foundIdx !== -1) {
        setDragState({ index: foundIdx, currentDistM: segments[foundIdx].end_dist });
        chart.options.plugins.tooltip.enabled = false;
    }
  };

  const handleMouseMove = (e) => {
    const chart = chartRef.current;
    if (!chart) return;
    if (dragState) {
        const rect = chart.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const newDistKm = chart.scales.x.getValueForPixel(mouseX);
        const newDistM = newDistKm * 1000;
        const currentSeg = segments[dragState.index];
        const nextSeg = segments[dragState.index + 1];
        if (newDistM > currentSeg.start_dist + 100 && newDistM < nextSeg.end_dist - 100) {
            setDragState(prev => ({ ...prev, currentDistM: newDistM }));
        }
    } else {
        const points = chart.getElementsAtEventForMode(e, 'nearest', { intersect: false, axis: 'x' }, true);
        if (points.length > 0) {
            const idx = points[0].index;
            const dsIdx = points[0].datasetIndex;
            const pt = chartData.datasets[dsIdx].data[idx];
            if (pt && pt.original_dist_m !== hoveredDist) setHoveredDist(pt.original_dist_m);
        }
    }
  };

  const handleMouseUp = (e) => {
    if (dragState) {
        moveSegmentBoundary(dragState.index, dragState.currentDistM);
        setDragState(null);
        if (chartRef.current) chartRef.current.options.plugins.tooltip.enabled = true;
    } else if (mouseDownPos) {
        const dist = Math.sqrt(Math.pow(e.clientX - mouseDownPos.x, 2) + Math.pow(e.clientY - mouseDownPos.y, 2));
        if (dist < 5) {
            const chart = chartRef.current;
            const rect = chart.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const clickDistKm = chart.scales.x.getValueForPixel(mouseX);
            const targetSeg = segments.find(s => (clickDistKm*1000) >= s.start_dist && (clickDistKm*1000) <= s.end_dist);
            if (targetSeg) toggleSegmentSelection(targetSeg.id, e.shiftKey);
        }
    }
    setMouseDownPos(null);
  };

  const handleContextMenu = (e) => {
      e.preventDefault();
      if (hoveredDist !== null && !dragState) splitSegment(hoveredDist);
  };

  if (!gpxData || gpxData.length === 0) return <div>Load GPX</div>;

  return (
    <div className="w-full bg-[#1E1E1E] rounded-xl border border-gray-800 p-4 mt-6 shadow-lg h-[300px]"
         onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>
      <h3 className="text-sm font-bold text-[#2a9e92] mb-2 uppercase tracking-wider">Elevation Profile</h3>
      <div className="w-full h-[230px]" onContextMenu={handleContextMenu} onMouseDown={handleMouseDown} onMouseMove={handleMouseMove}>
        <Line ref={chartRef} data={chartData} options={options} />
      </div>
    </div>
  );
};

export default ElevationChart;

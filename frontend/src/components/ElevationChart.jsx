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
    splitSegment, moveSegmentBoundary 
  } = useCourseStore();
  
  const chartRef = useRef(null);
  const [dragState, setDragState] = useState(null);

  // 1. Prepare Chart Data
  const chartData = useMemo(() => {
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
          pointHoverRadius: 0,
          borderWidth: 2,
        }
      ],
    };
  }, [gpxData]);

  // 2. Generate Annotations (Boxes & Lines)
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

      // Box Background
      elements[`box${i}`] = {
        type: 'box',
        xMin: effectiveStart / 1000,
        xMax: effectiveEnd / 1000,
        backgroundColor: seg.type === 'UP' 
          ? `rgba(244, 67, 54, ${isSelected ? 0.4 : 0.2})` 
          : (seg.type === 'DOWN' ? `rgba(0, 172, 193, ${isSelected ? 0.4 : 0.2})` : `rgba(255, 255, 255, ${isSelected ? 0.2 : 0})`),
        borderWidth: 0,
        // Safe click handler for selection
        click: (context) => {
            // Chart.js annotation plugin passes context which contains the event
            // Access logic: context.chart.canvas... or context.event
            // Sometimes context.event is the wrapper.
            const e = context.event; 
            const nativeEvent = e?.native || e; // Fallback
            if (nativeEvent) {
                toggleSegmentSelection(seg.id, nativeEvent.shiftKey);
            }
        }
      };

      // Boundary Line (Draggable)
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
          enter: (ctx) => {
             if (!dragState) ctx.chart.canvas.style.cursor = 'col-resize';
          },
          leave: (ctx) => {
             if (!dragState) ctx.chart.canvas.style.cursor = 'default';
          }
        };
      }
    });
    return elements;
  }, [segments, selectedSegmentIds, dragState]);

  // Options Definition
  const options = {
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
        backgroundColor: '#1E1E1E',
        callbacks: {
          label: (ctx) => `Ele: ${ctx.parsed.y}m`,
          title: (items) => `Dist: ${items[0].parsed.x}km`,
        }
      },
    },
    scales: {
      x: {
        type: 'linear',
        grid: { display: false },
        ticks: { color: '#666', callback: (v) => `${v}km` }
      },
      y: {
        grid: { color: '#333' },
        ticks: { color: '#666' }
      }
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false
    }
  };

  // --- Manual Event Handlers ---
  const handleMouseDown = (e) => {
    const chart = chartRef.current;
    if (!chart) return;

    const rect = chart.canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    
    let foundIdx = -1;
    let minDiff = Infinity;
    const HIT_TOLERANCE_PX = 10;

    for (let i = 0; i < segments.length - 1; i++) {
        const seg = segments[i];
        const segEndKm = seg.end_dist / 1000;
        const pixelX = chart.scales.x.getPixelForValue(segEndKm);
        
        const diff = Math.abs(mouseX - pixelX);
        if (diff < HIT_TOLERANCE_PX && diff < minDiff) {
            minDiff = diff;
            foundIdx = i;
        }
    }

    if (foundIdx !== -1) {
        setDragState({
            index: foundIdx,
            currentDistM: segments[foundIdx].end_dist
        });
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
        
        const minLimit = currentSeg.start_dist + 100;
        const maxLimit = nextSeg.end_dist - 100;

        if (newDistM > minLimit && newDistM < maxLimit) {
            setDragState(prev => ({ ...prev, currentDistM: newDistM }));
        }
    } else {
        const points = chart.getElementsAtEventForMode(e, 'nearest', { intersect: false, axis: 'x' }, true);
        if (points.length > 0) {
            const index = points[0].index;
            const dsIndex = points[0].datasetIndex;
            const pt = chartData.datasets[dsIndex].data[index];
            if (pt) {
                const d = pt.original_dist_m || (pt.x * 1000);
                if (hoveredDist !== d) setHoveredDist(d);
            }
        }
    }
  };

  const handleMouseUp = () => {
    if (dragState) {
        moveSegmentBoundary(dragState.index, dragState.currentDistM);
        setDragState(null);
        if (chartRef.current) chartRef.current.options.plugins.tooltip.enabled = true;
    }
  };

  const handleContextMenu = (e) => {
    e.preventDefault();
    if (hoveredDist !== null && !dragState) {
        splitSegment(hoveredDist);
    }
  };

  if (!gpxData || gpxData.length === 0) return <div>Load GPX</div>;

  return (
    <div className="w-full bg-[#1E1E1E] rounded-xl border border-gray-800 p-4 mt-6 shadow-lg h-[300px]">
      <h3 className="text-sm font-bold text-[#2a9e92] mb-2 uppercase tracking-wider">Elevation Profile</h3>
      <div 
        className="w-full h-[230px]" 
        onContextMenu={handleContextMenu}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <Line ref={chartRef} data={chartData} options={options} />
      </div>
    </div>
  );
};

export default ElevationChart;
import React, { useState, useEffect, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { PolygonLayer, ColumnLayer } from '@deck.gl/layers';
import { Map } from 'react-map-gl/maplibre';
import useCourseStore from '../stores/useCourseStore';
import 'maplibre-gl/dist/maplibre-gl.css';

const INITIAL_VIEW_STATE = {
  longitude: 126.99,
  latitude: 37.55,
  zoom: 13,
  pitch: 60,
  bearing: 30
};

const MapViewer = () => {
  const { gpxData, atomicSegments, segments, hoveredDist, setHoveredDist, selectedSegmentIds, toggleSegmentSelection, simulationResult } = useCourseStore();
  
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  
  const Z_SCALE = 5.0;

  // Recenter map when data is loaded
  useEffect(() => {
    if (gpxData.length > 0) {
      setViewState(prev => ({
        ...prev,
        longitude: gpxData[0].lon,
        latitude: gpxData[0].lat,
        zoom: 14
      }));
    }
  }, [gpxData]);

  // Find hovered point coordinates for the indicator
  const hoveredPoint = useMemo(() => {
    if (hoveredDist === null || gpxData.length === 0) return null;
    // Fallback: use gpxData for hover indicator position (it's fine)
    return gpxData.find(p => p.dist_m >= hoveredDist) || gpxData[gpxData.length-1];
  }, [hoveredDist, gpxData]);

  // Generate 3D Curtain Wall synced with Atomic Segments
  const curtainLayers = useMemo(() => {
    if (!atomicSegments || atomicSegments.length === 0) return [];

    const wallData = [];
    const EPSILON = 0.0001; // Tiny offset to give volume to vertical walls

    atomicSegments.forEach((as, idx) => {
      // Match with User Segment for color using Midpoint
      const midDist = (as.start_dist + as.end_dist) / 2;
      const userSeg = segments.find(s => midDist >= s.start_dist && midDist < s.end_dist);
      const currentSeg = userSeg || segments[0]; 
      
      const isSelected = selectedSegmentIds.includes(currentSeg?.id);

      // Color Logic
      let color = [165, 214, 167]; 
      if (isSelected) color = [255, 215, 0]; 
      else if (currentSeg?.type === 'UP') color = [244, 67, 54]; 
      else if (currentSeg?.type === 'DOWN') color = [0, 172, 193]; 

      // Build Polygon using Shifted Coordinates from Backend
      // Apply tiny EPSILON to top points to prevent zero-area culling of vertical walls
      const bl = [as.shifted_start_lon, as.shifted_start_lat, 0];
      const br = [as.shifted_end_lon, as.shifted_end_lat, 0];
      const tr = [as.shifted_end_lon + EPSILON, as.shifted_end_lat + EPSILON, as.end_ele * Z_SCALE];
      const tl = [as.shifted_start_lon + EPSILON, as.shifted_start_lat + EPSILON, as.start_ele * Z_SCALE];

      // Metadata for Tooltip
      const simStats = simulationResult?.track_data?.[idx] || null;

      wallData.push({ 
          polygon: [bl, br, tr, tl],
          color, 
          segmentId: currentSeg?.id,
          userSegment: currentSeg, // Link to parent
          dist_m: as.end_dist, 
          stats: simStats,
          grade: as.avg_grade
      });
    });

    return [
      new PolygonLayer({
        id: `curtain-wall-atomic-${atomicSegments.length}`,
        data: wallData,
        pickable: true,
        stroked: false,
        filled: true,
        extruded: false, // We provide explicit Z coordinates
        getPolygon: d => d.polygon,
        getFillColor: d => [...d.color, 255],
        parameters: {
          cull: false, // Draw double-sided
          depthTest: true
        },
        getPolygonOffset: ({layerIndex}) => [0, -1000],
        onHover: info => setHoveredDist(info.object?.dist_m || null),
        onClick: i => {
            if (i.object && i.object.segmentId) {
                const isShift = i.srcEvent ? i.srcEvent.shiftKey : false;
                toggleSegmentSelection(i.object.segmentId, isShift);
            }
        },
      })
    ];
  }, [atomicSegments, segments, selectedSegmentIds, simulationResult]);

  const getTooltip = ({object}) => {
    if (!object) return null;
    const { stats, grade, dist_m, segmentId } = object;
    
    let content = `Segment: #${segmentId}\nGrade: ${grade?.toFixed(1) || 0}%\nDist: ${(dist_m/1000).toFixed(2)}km`;
    
    if (stats) {
        content += `\n\n-- Simulation --\nPower: ${Math.round(stats.power)}W\nSpeed: ${stats.speed_kmh.toFixed(1)}km/h\nTime: ${Math.floor(stats.time_sec/60)}m ${Math.floor(stats.time_sec%60)}s`;
    }
    return content;
  };

  return (
    <div className="relative w-full h-[600px] rounded-xl overflow-hidden border border-gray-700 shadow-2xl bg-[#121212]">
      <DeckGL
        viewState={viewState}
        onViewStateChange={({viewState}) => setViewState(viewState)}
        controller={{
          dragRotate: true,
          scrollZoom: true,
          doubleClickZoom: true,
          touchRotate: true,
          maxPitch: 85,
          minPitch: 0
        }}
        layers={[...curtainLayers, ...(hoveredPoint ? [new ColumnLayer({
            id: 'hover-column',
            data: [hoveredPoint],
            getPosition: d => [d.lon, d.lat],
            getFillColor: [192, 38, 211, 255],
            getElevation: d => d.ele * Z_SCALE + 1000, 
            elevationScale: 1,
            radius: 100, 
            extruded: true,
            pickable: false,
            material: false
          })] : [])]}
        getTooltip={getTooltip}
        style={{position: 'absolute', top: 0, left: 0}}
      >
        <Map
          viewState={viewState}
          maxPitch={85}
          mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          reuseMaps
        />
      </DeckGL>
      
      <div className="absolute top-4 left-4 bg-[#1E1E1E]/80 backdrop-blur-md p-4 rounded-lg border border-gray-600 pointer-events-none z-10">
        <h3 className="text-[#2a9e92] font-bold text-lg">3D Course View</h3>
        <p className="text-xs text-gray-400">
          {atomicSegments.length > 0 ? "Course Data Loaded" : "Waiting for GPX upload..."}
        </p>
      </div>
    </div>
  );
};

export default MapViewer;
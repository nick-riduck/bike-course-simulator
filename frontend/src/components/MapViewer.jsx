import React, { useState, useEffect, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { PolygonLayer, ColumnLayer } from '@deck.gl/layers';
import { Map } from 'react-map-gl/maplibre';
import useCourseStore from '../stores/useCourseStore';
import 'maplibre-gl/dist/maplibre-gl.css';

// --- Constants ---
const INITIAL_VIEW_STATE = {
  longitude: 126.99,
  latitude: 37.55,
  zoom: 13,
  pitch: 60,
  bearing: 30
};

const MapViewer = () => {
  const { gpxData, hoveredDist } = useCourseStore();
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  
  const Z_SCALE = 5.0;
  const EPSILON = 0.0001; 

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
    
    let closest = gpxData[0];
    let minDiff = Infinity;
    
    for (const p of gpxData) {
      const diff = Math.abs(p.dist_m - hoveredDist);
      if (diff < minDiff) {
        minDiff = diff;
        closest = p;
      }
      if (diff > minDiff) break;
    }
    return closest;
  }, [hoveredDist, gpxData]);

  // Generate 3D Curtain Wall from real points (Unlit, 선명한 색상)
  const curtainLayers = useMemo(() => {
    if (gpxData.length < 2) return [];

    const wallData = [];
    for (let i = 1; i < gpxData.length; i++) {
      const p1 = gpxData[i - 1];
      const p2 = gpxData[i];

      let color = [165, 214, 167]; // Flat
      if (p2.grade_pct > 2.0) color = [244, 67, 54]; // Uphill
      else if (p2.grade_pct < -2.0) color = [0, 172, 193]; // Downhill

      const bl = [p1.lon, p1.lat, 0];
      const br = [p2.lon, p2.lat, 0];
      const tr = [p2.lon + EPSILON, p2.lat + EPSILON, p2.ele * Z_SCALE];
      const tl = [p1.lon + EPSILON, p1.lat + EPSILON, p1.ele * Z_SCALE];

      wallData.push({ polygon: [bl, br, tr], color, grade_pct: p2.grade_pct });
      wallData.push({ polygon: [bl, tr, tl], color, grade_pct: p2.grade_pct });
    }

    return [
      new PolygonLayer({
        id: 'curtain-wall-real',
        data: wallData,
        pickable: true,
        stroked: false,
        filled: true,
        extruded: false,
        getPolygon: d => d.polygon,
        getFillColor: d => [...d.color, 255],
        parameters: {
          cull: false,
          depthTest: true
        },
        getPolygonOffset: ({layerIndex}) => [0, -1000]
      })
    ];
  }, [gpxData]);

  const layers = [
    ...curtainLayers,
    // Hover Column Indicator (The Purple Pillar - Restored)
    ...(hoveredPoint ? [
      new ColumnLayer({
        id: 'hover-column',
        data: [hoveredPoint],
        getPosition: d => [d.lon, d.lat],
        getFillColor: [192, 38, 211, 255], // Brighter Neon Purple
        getElevation: d => d.ele * Z_SCALE * 1.5 + 1000, 
        elevationScale: 1,
        radius: 50, 
        extruded: true,
        pickable: false,
        material: false,
        getPolygonOffset: ({layerIndex}) => [0, -5000]
      })
    ] : [])
  ];

  return (
    <div className="relative w-full h-[600px] rounded-xl overflow-hidden border border-gray-700 shadow-2xl bg-[#121212]">
      <DeckGL
        viewState={viewState}
        onViewStateChange={({viewState}) => setViewState(viewState)}
        controller={true}
        layers={layers}
        getTooltip={({object}) => object && `Grade: ${object.grade_pct?.toFixed(1) || 'N/A'}%`}
        style={{position: 'absolute', top: 0, left: 0}}
      >
        <Map
          mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          reuseMaps
        />
      </DeckGL>
      
      <div className="absolute top-4 left-4 bg-riduck-card/80 backdrop-blur-md p-4 rounded-lg border border-gray-600 pointer-events-none z-10">
        <h3 className="text-riduck-primary font-bold text-lg">3D Course View</h3>
        <p className="text-xs text-gray-400">
          {gpxData.length > 0 ? "Course Data Loaded" : "Waiting for GPX upload..."}
        </p>
      </div>
    </div>
  );
};

export default MapViewer;

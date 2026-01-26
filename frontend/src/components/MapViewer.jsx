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
  const { gpxData, hoveredDist, segments, selectedSegmentIds } = useCourseStore();
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

  // Helper: Shift a point along a bearing
  const shiftPoint = (lon, lat, bearing, dist) => {
    const R = 6378137;
    const d = dist;
    const brng = bearing * (Math.PI / 180);
    const lat1 = lat * (Math.PI / 180);
    const lon1 = lon * (Math.PI / 180);

    const lat2 = Math.asin(Math.sin(lat1) * Math.cos(d / R) + Math.cos(lat1) * Math.sin(d / R) * Math.cos(brng));
    const lon2 = lon1 + Math.atan2(Math.sin(brng) * Math.sin(d / R) * Math.cos(lat1), Math.cos(d / R) - Math.sin(lat1) * Math.sin(lat2));
    
    return [lon2 * (180 / Math.PI), lat2 * (180 / Math.PI)];
  };

  // Helper: Calculate bearing
  const getBearing = (startLat, startLng, destLat, destLng) => {
    const startLatRad = startLat * (Math.PI / 180);
    const startLngRad = startLng * (Math.PI / 180);
    const destLatRad = destLat * (Math.PI / 180);
    const destLngRad = destLng * (Math.PI / 180);

    const y = Math.sin(destLngRad - startLngRad) * Math.cos(destLatRad);
    const x = Math.cos(startLatRad) * Math.sin(destLatRad) -
              Math.sin(startLatRad) * Math.cos(destLatRad) * Math.cos(destLngRad - startLngRad);
    const brng = Math.atan2(y, x);
    return ((brng * 180) / Math.PI + 360) % 360;
  };

  // Generate 3D Curtain Wall synced with Segments
  const curtainLayers = useMemo(() => {
    if (gpxData.length < 2 || segments.length === 0) return [];

    const wallData = [];
    const OFFSET_M = 15; // Shift distance
    const shiftedPoints = [];

    // 1. Pre-calculate Shifted Vertices
    for (let i = 0; i < gpxData.length; i++) {
      const curr = gpxData[i];
      let bearing;

      if (i === 0) {
        const next = gpxData[i + 1];
        const b = getBearing(curr.lat, curr.lon, next.lat, next.lon);
        bearing = b + 90;
      } else if (i === gpxData.length - 1) {
        const prev = gpxData[i - 1];
        const b = getBearing(prev.lat, prev.lon, curr.lat, curr.lon);
        bearing = b + 90;
      } else {
        const prev = gpxData[i - 1];
        const next = gpxData[i + 1];
        const b1 = getBearing(prev.lat, prev.lon, curr.lat, curr.lon);
        const b2 = getBearing(curr.lat, curr.lon, next.lat, next.lon);
        
        let avgBearing = (b1 + b2) / 2;
        if (Math.abs(b1 - b2) > 180) avgBearing += 180;
        bearing = avgBearing + 90; 
      }
      const shifted = shiftPoint(curr.lon, curr.lat, bearing, OFFSET_M);
      shiftedPoints.push(shifted);
    }

    // 2. Build Wall using Shifted Vertices
    let segIdx = 0;
    for (let i = 1; i < gpxData.length; i++) {
      const p1 = gpxData[i - 1];
      const p2 = gpxData[i];
      const s1 = shiftedPoints[i - 1];
      const s2 = shiftedPoints[i];
      const dist = p2.dist_m;

      // Find segment
      while (segIdx < segments.length - 1 && dist > segments[segIdx].end_dist) {
        segIdx++;
      }
      const currentSeg = segments[segIdx];
      const isSelected = selectedSegmentIds.includes(currentSeg.id);

      // Color logic with selection highlight
      let color = [165, 214, 167]; 
      if (isSelected) color = [255, 215, 0]; // Gold for selection
      else if (currentSeg.type === 'UP') color = [244, 67, 54]; 
      else if (currentSeg.type === 'DOWN') color = [0, 172, 193]; 

      const bl = [s1[0], s1[1], 0];
      const br = [s2[0], s2[1], 0];
      const tr = [s2[0] + EPSILON, s2[1] + EPSILON, p2.ele * Z_SCALE];
      const tl = [s1[0] + EPSILON, s1[1] + EPSILON, p1.ele * Z_SCALE];

      wallData.push({ polygon: [bl, br, tr], color });
      wallData.push({ polygon: [bl, tr, tl], color });
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
  }, [gpxData, segments, selectedSegmentIds]);

  const layers = [
    ...curtainLayers,
    // Hover Column Indicator (Restored)
    ...(hoveredPoint ? [
      new ColumnLayer({
        id: 'hover-column',
        data: [hoveredPoint],
        getPosition: d => [d.lon, d.lat],
        getFillColor: [192, 38, 211, 255], // Brighter Neon Purple
        getElevation: d => d.ele * Z_SCALE * 1.5 + 1000, 
        elevationScale: 1,
        radius: 100, // Massive radius for visibility
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
        controller={{
          dragRotate: true,
          scrollZoom: true,
          doubleClickZoom: true,
          touchRotate: true,
          maxPitch: 85, // Allowed to tilt almost flat
          minPitch: 0
        }}
        layers={layers}
        getTooltip={({object}) => object && `Grade: ${object.grade_pct?.toFixed(1) || 'N/A'}%`}
        style={{position: 'absolute', top: 0, left: 0}}
      >
        <Map
          viewState={viewState}
          maxPitch={85} // Match DeckGL pitch limit
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
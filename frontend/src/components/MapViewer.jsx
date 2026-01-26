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
  const { gpxData, hoveredDist, segments } = useCourseStore();
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

  // Helper: Calculate offset point (15m to the right)
  const getOffsetPoint = (lon, lat, bearing, offsetMeters = 15) => {
    const R = 6378137; // Earth Radius
    const d = offsetMeters;
    const brng = (bearing + 90) * (Math.PI / 180); // Right 90 degrees
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
    let segIdx = 0;

    for (let i = 1; i < gpxData.length; i++) {
      const p1 = gpxData[i - 1];
      const p2 = gpxData[i];
      const dist = p2.dist_m;

      // Find which segment this point belongs to
      while (segIdx < segments.length - 1 && dist > segments[segIdx].end_dist) {
        segIdx++;
      }
      const currentSeg = segments[segIdx];

      // Color based on Segment Type
      let color = [165, 214, 167]; // FLAT
      if (currentSeg.type === 'UP') color = [244, 67, 54]; // UP
      else if (currentSeg.type === 'DOWN') color = [0, 172, 193]; // DOWN

      // Apply Offset for 2-way separation
      const bearing = getBearing(p1.lat, p1.lon, p2.lat, p2.lon);
      const [oLon1, oLat1] = getOffsetPoint(p1.lon, p1.lat, bearing);
      const [oLon2, oLat2] = getOffsetPoint(p2.lon, p2.lat, bearing);

      const bl = [oLon1, oLat1, 0];
      const br = [oLon2, oLat2, 0];
      const tr = [oLon2 + EPSILON, oLat2 + EPSILON, p2.ele * Z_SCALE];
      const tl = [oLon1 + EPSILON, oLat1 + EPSILON, p1.ele * Z_SCALE];

      wallData.push({ polygon: [bl, br, tr], color });
      wallData.push({ polygon: [bl, tr, tl], color });
    }
    // ... (return PolygonLayer same) ...

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
        controller={{
          dragRotate: true,
          scrollZoom: true,
          doubleClickZoom: true,
          touchRotate: true,
          maxPitch: 85,
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

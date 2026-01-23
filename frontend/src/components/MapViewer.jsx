import React, { useState } from 'react';
import DeckGL from '@deck.gl/react';
import { PolygonLayer, ScatterplotLayer } from '@deck.gl/layers';
import { Map } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

// --- Constants ---
const INITIAL_VIEW_STATE = {
  longitude: 126.99,
  latitude: 37.55,
  zoom: 13,
  pitch: 60,
  bearing: 30
};

const DUMMY_COURSE = [
  { start: [126.990, 37.550, 100], end: [126.992, 37.552, 120], color: [244, 67, 54] },
  { start: [126.992, 37.552, 120], end: [126.995, 37.555, 120], color: [165, 214, 167] },
  { start: [126.995, 37.555, 120], end: [127.000, 37.560, 90], color: [0, 172, 193] },
];

const MapViewer = () => {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const Z_SCALE = 5.0;
  
  // CRITICAL: Tiny offset to give vertical walls non-zero area on XY plane
  const EPSILON = 0.0001; 

  // Process data into simple triangles with offset
  const triangleData = DUMMY_COURSE.flatMap(d => {
    const s = d.start;
    const e = d.end;
    const bl = [s[0], s[1], 0];
    const br = [e[0], e[1], 0];
    const tr = [e[0] + EPSILON, e[1] + EPSILON, e[2] * Z_SCALE];
    const tl = [s[0] + EPSILON, s[1] + EPSILON, s[2] * Z_SCALE];

    return [
      { polygon: [bl, br, tr], color: d.color },
      { polygon: [bl, tr, tl], color: d.color }
    ];
  });

  const pointData = DUMMY_COURSE.map(d => ({ position: d.start }));

  const layers = [
    // Curtain Wall
    new PolygonLayer({
      id: 'curtain-wall',
      data: triangleData,
      pickable: true,
      extruded: false,
      wireframe: false, 
      filled: true,
      stroked: false, // Remove outline to show pure fill color
      lineWidthMinPixels: 0,
      getPolygon: d => d.polygon,
      getFillColor: d => [...d.color, 255],
      // getLineColor: [255, 255, 255, 50],
      parameters: {
        cull: false,
        depthTest: true
      },
      getPolygonOffset: ({layerIndex}) => [0, -1000]
    })
  ];

  return (
    <div className="relative w-full h-[600px] rounded-xl overflow-hidden border border-gray-700 shadow-2xl bg-[#121212]">
      <DeckGL
        viewState={viewState}
        onViewStateChange={({viewState}) => setViewState(viewState)}
        controller={true}
        layers={layers}
        getTooltip={({object}) => object && `Debug Object`}
        style={{position: 'absolute', top: 0, left: 0}}
      >
        <Map
          mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          reuseMaps
        />
      </DeckGL>
      
      <div className="absolute top-4 left-4 bg-riduck-card/80 backdrop-blur-md p-4 rounded-lg border border-gray-600 pointer-events-none z-10">
        <h3 className="text-riduck-primary font-bold text-lg">3D Course View</h3>
        <p className="text-xs text-gray-400">Drag to rotate • Scroll to zoom</p>
      </div>
    </div>
  );
};

export default MapViewer;
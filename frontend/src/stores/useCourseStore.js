import { create } from 'zustand';
import { XMLParser } from 'fast-xml-parser';

const useCourseStore = create((set, get) => ({
  gpxData: [], // Array of {lat, lon, ele, dist_m, grade_pct}
  segments: [], // Array of {id, start_dist, end_dist, type, target_power}
  hoveredDist: null, // Distance in meters where the mouse is hovering
  riderProfile: {
    weight_kg: 70,
    ftp: 250,
  },

  // --- Actions ---
  setHoveredDist: (dist) => set({ hoveredDist: dist }),

  // Parse GPX XML string into internal data structure
  loadGpxFromXml: (xmlString) => {
    const parser = new XMLParser({ ignoreAttributes: false });
    const jsonObj = parser.parse(xmlString);
    
    // Support standard GPX structure: gpx.trk.trkseg.trkpt
    const trkpts = jsonObj?.gpx?.trk?.trkseg?.trkpt;
    if (!trkpts || !Array.isArray(trkpts)) {
      console.error("Invalid GPX format: Could not find track points.");
      return;
    }

    const points = [];
    let totalDist = 0;

    const toRad = (deg) => (deg * Math.PI) / 180;
    const haversine = (p1, p2) => {
      const R = 6371000; // meters
      const dLat = toRad(p2.lat - p1.lat);
      const dLon = toRad(p2.lon - p1.lon);
      const a = 
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(toRad(p1.lat)) * Math.cos(toRad(p2.lat)) * 
        Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    };

    trkpts.forEach((pt, i) => {
      const lat = parseFloat(pt['@_lat']);
      const lon = parseFloat(pt['@_lon']);
      const ele = parseFloat(pt.ele || 0);
      
      let dist_m = 0;
      let grade_pct = 0;

      if (i > 0) {
        const prev = points[i-1];
        const stepDist = haversine(prev, {lat, lon});
        totalDist += stepDist;
        dist_m = totalDist;
        
        if (stepDist > 0) {
          grade_pct = ((ele - prev.ele) / stepDist) * 100;
        }
      }

      points.push({ lat, lon, ele, dist_m, grade_pct });
    });

    // Auto-generate segments based on grade changes (Adaptive Segmentation)
    const segments = [];
    let startIdx = 0;
    
    const getTerrainType = (grade) => {
      if (grade > 3.5) return "UP";
      if (grade < -3.5) return "DOWN";
      return "FLAT";
    };

    let currentType = getTerrainType(points[0].grade_pct);
    
    for (let i = 1; i < points.length; i++) {
      const p = points[i];
      const distFromStartOfSeg = p.dist_m - points[startIdx].dist_m;
      const terrainType = getTerrainType(p.grade_pct);

      // Trigger split if terrain type changes and minimum distance (200m) is met
      const isTypeChange = terrainType !== currentType;
      const isMinDistMet = distFromStartOfSeg > 200; // Restored to 200m
      const isLastPoint = i === points.length - 1;

      if ((isTypeChange && isMinDistMet) || isLastPoint) {
        // ... (rest is same)
        segments.push({
          id: segments.length + 1,
          name: `Segment ${segments.length + 1}`,
          start_dist: points[startIdx].dist_m,
          end_dist: p.dist_m,
          type: currentType,
          target_power: currentType === "UP" ? get().riderProfile.ftp * 1.1 : get().riderProfile.ftp * 0.8
        });
        
        startIdx = i;
        currentType = terrainType;
      }
    }

    set({ gpxData: points, segments });
    console.log(`Loaded GPX: ${points.length} points, ${segments.length} segments`);
  },

  // Split a segment at a given distance
  splitSegment: (splitDist) => {
    const { segments } = get();
    const newSegments = [];
    
    segments.forEach(seg => {
      if (splitDist > seg.start_dist && splitDist < seg.end_dist) {
        // Cut here
        newSegments.push({
          ...seg,
          end_dist: splitDist,
          name: `${seg.name} (Part 1)`
        });
        newSegments.push({
          ...seg,
          id: Date.now(), // Unique ID
          start_dist: splitDist,
          name: `${seg.name} (Part 2)`
        });
      } else {
        newSegments.push(seg);
      }
    });

    set({ segments: newSegments.sort((a, b) => a.start_dist - b.start_dist) });
  },

  updateRiderProfile: (profile) => set((state) => ({
    riderProfile: { ...state.riderProfile, ...profile }
  })),

  // Update a single segment's property
  updateSegment: (id, updates) => set((state) => ({
    segments: state.segments.map(s => s.id === id ? { ...s, ...updates } : s)
  })),
}));

export default useCourseStore;

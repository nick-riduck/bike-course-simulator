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

    // 1. Initial Segmentation (Adaptive)
    let rawSegments = [];
    let startIdx = 0;
    const GRADE_THRESHOLD = 3.5; 
    const MIN_SEG_DIST = 200;    

    // Calculate grade between two points
    const calcGrade = (p1, p2) => {
      const d = p2.dist_m - p1.dist_m;
      if (d === 0) return 0;
      return ((p2.ele - p1.ele) / d) * 100;
    };

    const getTerrainType = (g) => {
      if (g > 3.5) return "UP";
      if (g < -3.5) return "DOWN";
      return "FLAT";
    };

    let refGrade = calcGrade(points[0], points[Math.min(5, points.length-1)]);

    for (let i = 1; i < points.length; i++) {
      const startPt = points[startIdx];
      const currPt = points[i];
      const segDist = currPt.dist_m - startPt.dist_m;
      
      // Instantaneous grade (smoothed over last few points)
      const instantGrade = i > 5 ? calcGrade(points[i-5], currPt) : calcGrade(points[i-1], currPt);

      // Check trigger conditions
      const gradeChange = Math.abs(instantGrade - refGrade);
      const isSignificant = gradeChange > GRADE_THRESHOLD && segDist > MIN_SEG_DIST;
      const isLast = i === points.length - 1;

      if (isSignificant || isLast) {
        // Create segment based on average grade of the chunk
        const avgGrade = ((currPt.ele - startPt.ele) / segDist) * 100;
        const type = getTerrainType(avgGrade);
        
        rawSegments.push({
          start_dist: startPt.dist_m,
          end_dist: currPt.dist_m,
          type: type,
          avg_grade: avgGrade,
          start_idx: startIdx,
          end_idx: i
        });
        
        startIdx = i;
        refGrade = instantGrade; // Adapt reference to new terrain
      }
    }

    // 2. Post-processing: Merge adjacent same-type segments
    if (rawSegments.length === 0 && points.length > 0) {
       // Fallback for very short courses
       const totalDist = points[points.length-1].dist_m;
       rawSegments.push({start_dist:0, end_dist: totalDist, type: getTerrainType(0), avg_grade: 0});
    }

    const mergedSegments = [];
    if (rawSegments.length > 0) {
      let current = rawSegments[0];
      
      for (let k = 1; k < rawSegments.length; k++) {
        const next = rawSegments[k];
        if (current.type === next.type) {
          // Merge
          current.end_dist = next.end_dist;
          // Re-calculate weighted average grade if needed, but for display type it's same
        } else {
          // Push and move next
          mergedSegments.push(current);
          current = next;
        }
      }
      mergedSegments.push(current);
    }

    // 3. Finalize
    const finalSegments = mergedSegments.map((s, idx) => ({
      id: idx + 1,
      name: `Segment ${idx + 1}`,
      start_dist: s.start_dist,
      end_dist: s.end_dist,
      type: s.type,
      target_power: s.type === "UP" ? get().riderProfile.ftp * 1.1 : get().riderProfile.ftp * 0.8
    }));

        set({ gpxData: points, segments: finalSegments });

        console.log(`Loaded GPX: ${points.length} points, ${finalSegments.length} segments`);

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
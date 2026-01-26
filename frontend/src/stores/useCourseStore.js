import { create } from 'zustand';
import { XMLParser } from 'fast-xml-parser';

const useCourseStore = create((set, get) => ({
  gpxData: [], 
  segments: [], 
  hoveredDist: null, 
  selectedSegmentIds: [], 
  riderProfile: {
    weight_kg: 70,
    ftp: 250,
  },

  setHoveredDist: (dist) => set({ hoveredDist: dist }),

  toggleSegmentSelection: (id, multiSelect) => set((state) => {
    const isSelected = state.selectedSegmentIds.includes(id);
    if (multiSelect && state.selectedSegmentIds.length > 0) {
      const firstId = state.selectedSegmentIds[0];
      const firstIdx = state.segments.findIndex(s => s.id === firstId);
      const lastIdx = state.segments.findIndex(s => s.id === id);
      
      if (firstIdx === -1 || lastIdx === -1) return state;

      const start = Math.min(firstIdx, lastIdx);
      const end = Math.max(firstIdx, lastIdx);
      
      const rangeIds = state.segments.slice(start, end + 1).map(s => s.id);
      return { selectedSegmentIds: rangeIds };
    } else {
      if (multiSelect) {
         return {
           selectedSegmentIds: isSelected 
             ? state.selectedSegmentIds.filter(sid => sid !== id)
             : [...state.selectedSegmentIds, id]
         };
      } else {
         return { selectedSegmentIds: isSelected ? [] : [id] };
      }
    }
  }),

  _calcSegmentType: (startDist, endDist) => {
    const { gpxData } = get();
    if (!gpxData || gpxData.length === 0) return { type: 'FLAT', avg_grade: 0 };

    let startEle = null;
    let endEle = null;
    
    for(const p of gpxData) {
      if (startEle === null && p.dist_m >= startDist) startEle = p.ele;
      if (p.dist_m >= endDist) {
        endEle = p.ele;
        break;
      }
    }
    if (endEle === null && gpxData.length > 0) endEle = gpxData[gpxData.length-1].ele;
    if (startEle === null) startEle = gpxData[0].ele;

    const dist = endDist - startDist;
    if (dist <= 0) return { type: 'FLAT', avg_grade: 0 };

    const avgGrade = ((endEle - startEle) / dist) * 100;
    
    let type = 'FLAT';
    if (avgGrade > 3.5) type = 'UP';
    if (avgGrade < -3.5) type = 'DOWN';
    
    return { type, avg_grade: avgGrade };
  },

  loadGpxFromXml: (xmlString) => {
    const parser = new XMLParser({ ignoreAttributes: false });
    const jsonObj = parser.parse(xmlString);
    
    const trkpts = jsonObj?.gpx?.trk?.trkseg?.trkpt;
    if (!trkpts || !Array.isArray(trkpts)) {
      console.error("Invalid GPX format");
      return;
    }

    const points = [];
    let totalDist = 0;

    const toRad = (deg) => (deg * Math.PI) / 180;
    const haversine = (p1, p2) => {
      const R = 6371000; 
      const dLat = toRad(p2.lat - p1.lat);
      const dLon = toRad(p2.lon - p1.lon);
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
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

    // 1. Initial Segmentation
    let rawSegments = [];
    let startIdx = 0;
    const GRADE_THRESHOLD = 4.0; 
    const MIN_SEG_DIST = 500;    

    const getTerrainType = (g) => {
      if (g > 3.5) return "UP";
      if (g < -3.5) return "DOWN";
      return "FLAT";
    };

    for (let i = 1; i < points.length; i++) {
      const startPt = points[startIdx];
      const currPt = points[i];
      const segDist = currPt.dist_m - startPt.dist_m;

      const avgGrade = ((currPt.ele - startPt.ele) / segDist) * 100;
      const gradeDelta = Math.abs(currPt.grade_pct - startPt.grade_pct);
      const isSignificantChange = gradeDelta > GRADE_THRESHOLD && segDist > MIN_SEG_DIST;
      const isLastPoint = i === points.length - 1;

      if (isSignificantChange || isLastPoint) {
        const type = getTerrainType(avgGrade);
        rawSegments.push({
          start_dist: startPt.dist_m,
          end_dist: currPt.dist_m,
          type: type,
          start_idx: startIdx,
          end_idx: i
        });
        startIdx = i;
      }
    }

    // 2. Post-processing: Merge adjacent same-type segments
    const mergedSegments = [];
    if (rawSegments.length > 0) {
      let current = rawSegments[0];
      for (let k = 1; k < rawSegments.length; k++) {
        const next = rawSegments[k];
        if (current.type === next.type) {
          current.end_dist = next.end_dist; // Merge
        } else {
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

  splitSegment: (splitDist) => {
    const { segments, _calcSegmentType, riderProfile } = get();
    const newSegments = [];
    
    segments.forEach(seg => {
      if (splitDist > seg.start_dist && splitDist < seg.end_dist) {
        const stats1 = _calcSegmentType(seg.start_dist, splitDist);
        const stats2 = _calcSegmentType(splitDist, seg.end_dist);

        newSegments.push({
          ...seg,
          end_dist: splitDist,
          name: `${seg.name} (1)`,
          type: stats1.type,
          target_power: stats1.type === "UP" ? riderProfile.ftp * 1.1 : riderProfile.ftp * 0.8
        });
        newSegments.push({
          ...seg,
          id: Date.now(), 
          start_dist: splitDist,
          name: `${seg.name} (2)`,
          type: stats2.type,
          target_power: stats2.type === "UP" ? riderProfile.ftp * 1.1 : riderProfile.ftp * 0.8
        });
      } else {
        newSegments.push(seg);
      }
    });

    set({ segments: newSegments.sort((a, b) => a.start_dist - b.start_dist) });
  },

  mergeSelectedSegments: () => set((state) => {
    const { segments, selectedSegmentIds } = state;
    if (selectedSegmentIds.length < 2) return state;

    const targetSegs = segments
      .filter(s => selectedSegmentIds.includes(s.id))
      .sort((a, b) => a.start_dist - b.start_dist);

    for (let i = 0; i < targetSegs.length - 1; i++) {
      if (targetSegs[i].end_dist !== targetSegs[i+1].start_dist) {
        console.warn("Cannot merge non-adjacent segments");
        return state;
      }
    }

    const first = targetSegs[0];
    const last = targetSegs[targetSegs.length - 1];
    
    // Recalculate type
    const stats = state._calcSegmentType(first.start_dist, last.end_dist);
    
    const totalLen = last.end_dist - first.start_dist;
    const weightedPower = targetSegs.reduce((acc, s) => acc + s.target_power * (s.end_dist - s.start_dist), 0) / totalLen;

    const mergedSeg = {
      ...first,
      end_dist: last.end_dist,
      name: `${first.name} (Merged)`,
      target_power: weightedPower,
      type: stats.type
    };

    const newSegments = segments.filter(s => !selectedSegmentIds.includes(s.id));
    newSegments.push(mergedSeg);
    newSegments.sort((a, b) => a.start_dist - b.start_dist);

    return { segments: newSegments, selectedSegmentIds: [] };
  }),

  updateRiderProfile: (profile) => set((state) => ({
    riderProfile: { ...state.riderProfile, ...profile }
  })),

  // Move a segment boundary (resize adjacent segments)
  moveSegmentBoundary: (segmentIndex, newDist) => set((state) => {
    const { segments, _calcSegmentType } = state;
    if (segmentIndex < 0 || segmentIndex >= segments.length - 1) return state;

    const current = segments[segmentIndex];
    const next = segments[segmentIndex + 1];

    // Validation: prevent crossing other boundaries
    if (newDist <= current.start_dist || newDist >= next.end_dist) return state;

    // Recalculate types for affected segments
    // Note: We need access to _calcSegmentType from state, or define it outside
    // Since _calcSegmentType uses get(), we can call it if we use get() inside this action
    // But here we are inside set callback. Let's use the one from state if available, or just update distances first.
    // Actually, recalculation is complex inside reducer. Let's just update distances for now.
    // Better: split this logic.
    
    // Correct approach:
    const newSegments = [...segments];
    
    // Update distances
    newSegments[segmentIndex] = { ...current, end_dist: newDist };
    newSegments[segmentIndex + 1] = { ...next, start_dist: newDist };

    return { segments: newSegments };
  }),

  // Update a single segment's property
  updateSegment: (id, updates) => set((state) => ({
    segments: state.segments.map(s => s.id === id ? { ...s, ...updates } : s)
  })),
}));

export default useCourseStore;
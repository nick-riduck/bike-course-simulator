import { create } from 'zustand';

const useCourseStore = create((set, get) => ({
  gpxData: [], 
  atomicSegments: [], // New: Physics-level segments from backend
  segments: [], // User-level clustered segments
  hoveredDist: null, 
  selectedSegmentIds: [], 
  simulationResult: null,
  riderProfile: {
    weight_kg: 70,
    ftp: 250,
    bike_weight: 8.5,
    w_prime: 20000
  },

  setHoveredDist: (dist) => set({ hoveredDist: dist }),

  // Unified Grade & Type calculation (used during clustering)
  _getStatsForRange: (startDist, endDist) => {
    const { gpxData } = get();
    if (!gpxData.length) return { type: 'FLAT', avg_grade: 0 };
    const pStart = gpxData.find(p => p.dist_m >= startDist) || gpxData[0];
    const pEnd = gpxData.find(p => p.dist_m >= endDist) || gpxData[gpxData.length-1];
    const d = pEnd.dist_m - pStart.dist_m;
    const g = d > 0 ? ((pEnd.ele - pStart.ele) / d) * 100 : 0;
    return { avg_grade: g, type: g > 3.5 ? 'UP' : (g < -3.5 ? 'DOWN' : 'FLAT') };
  },

  // Apply simulation results to user segments
  _applySimulationStats: (userSegments, simData = null) => {
    const result = simData || get().simulationResult;
    if (!result || !result.track_data) return userSegments;
    const track = result.track_data;
    return userSegments.map(seg => {
      const relevant = track.filter(p => (p.dist_km * 1000) > seg.start_dist && (p.dist_km * 1000) <= seg.end_dist);
      if (relevant.length > 0) {
        const startT = track.findLast(p => (p.dist_km * 1000) <= seg.start_dist)?.time_sec || 0;
        const duration = relevant[relevant.length - 1].time_sec - startT;
        const avgPower = relevant.reduce((sum, p) => sum + p.power, 0) / relevant.length;
        return { ...seg, simulated_duration: duration, simulated_avg_power: avgPower };
      }
      return seg;
    });
  },

  // New: Load GPX via Backend Preprocessing
  uploadGpx: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8123/upload_gpx', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) throw new Error('Upload failed');
      const data = await response.json();

      // Preprocess points to add grade_pct (Backend doesn't provide it per point)
      const pointsWithGrade = data.points.map((p, i, arr) => {
          let grade = 0;
          if (i > 0) {
              const prev = arr[i-1];
              const d = p.dist_m - prev.dist_m;
              if (d > 0) grade = ((p.ele - prev.ele) / d) * 100;
          }
          return { ...p, grade_pct: grade };
      });

      // data.points, data.atomic_segments
      set({ gpxData: data.points, atomicSegments: data.atomic_segments });

      // --- Advanced Clustering Logic ---
      
      // 1. Assign Initial Types
      let workSegments = data.atomic_segments.map(as => ({
          ...as,
          type: as.avg_grade > 3.5 ? 'UP' : (as.avg_grade < -3.5 ? 'DOWN' : 'FLAT'),
          length: as.end_dist - as.start_dist
      }));

      // 2. Pass 1: Sandwich Smoothing (Noise Reduction)
      // Look for patterns like A-B-A where B is short and weak
      for (let i = 1; i < workSegments.length - 1; i++) {
          const prev = workSegments[i-1];
          const curr = workSegments[i];
          const next = workSegments[i+1];

          if (prev.type === next.type && curr.type !== prev.type) {
              // Condition: Short length AND grade isn't too extreme compared to neighbors
              // e.g. UP(5%) - FLAT(1%) - UP(6%) -> Merge
              // e.g. UP(5%) - DOWN(-10%) - UP(6%) -> Keep (Extreme change)
              
              const isShort = curr.length < 500; // 500m threshold
              const gradeDiff = Math.abs(curr.avg_grade - prev.avg_grade);
              const isWeak = gradeDiff < 5.0; // If grade change is within 5%, it's noise

              if (isShort && isWeak) {
                  curr.type = prev.type; // Absorb into the group
              }
          }
      }

      // 3. Explicit Clustering (Merge same adjacent types)
      const clusteredSegments = [];
      if (workSegments.length > 0) {
          let currentGroupStart = workSegments[0].start_dist;
          let currentType = workSegments[0].type;
          
          for (let i = 1; i < workSegments.length; i++) {
              const ws = workSegments[i];
              if (ws.type !== currentType) {
                  // Commit current group
                  const prevEnd = workSegments[i-1].end_dist;
                  const stats = get()._getStatsForRange(currentGroupStart, prevEnd);
                  
                  clusteredSegments.push({
                      id: 0, // Temp ID
                      start_dist: currentGroupStart,
                      end_dist: prevEnd,
                      type: currentType,
                      avg_grade: stats.avg_grade,
                      target_power: currentType === 'UP' ? 270 : 200
                  });
                  
                  // Start new group
                  currentGroupStart = ws.start_dist;
                  currentType = ws.type;
              }
          }
          // Commit last group
          const lastEnd = workSegments[workSegments.length - 1].end_dist;
          const stats = get()._getStatsForRange(currentGroupStart, lastEnd);
          clusteredSegments.push({
              id: 0,
              start_dist: currentGroupStart,
              end_dist: lastEnd,
              type: currentType,
              avg_grade: stats.avg_grade,
              target_power: currentType === 'UP' ? 270 : 200
          });
      }

      // 4. Pass 2: Aggressive Smoothing (Grade Diff < 2%)
      let mergedSegments = [...clusteredSegments];
      let changed = true;
      
      while (changed) {
          changed = false;
          const nextPass = [];
          if (mergedSegments.length === 0) break;
          
          let current = mergedSegments[0];
          
          for (let i = 1; i < mergedSegments.length; i++) {
              const next = mergedSegments[i];
              const gradeDiff = Math.abs(current.avg_grade - next.avg_grade);
              const isShort = (current.end_dist - current.start_dist) < 300 || (next.end_dist - next.start_dist) < 300;
              
              // Merge if same type OR similar grade OR noise
              if (current.type === next.type || gradeDiff < 2.0 || isShort) {
                  current.end_dist = next.end_dist;
                  const stats = get()._getStatsForRange(current.start_dist, current.end_dist);
                  current.avg_grade = stats.avg_grade;
                  current.type = stats.type; // Update type based on new average
                  changed = true;
              } else {
                  nextPass.push(current);
                  current = next;
              }
          }
          nextPass.push(current);
          mergedSegments = nextPass;
      }
      
      // Re-index IDs
      const finalUserSegments = mergedSegments.map((s, idx) => ({ ...s, id: idx + 1, name: `Segment ${idx + 1}` }));

      set({ segments: finalUserSegments, simulationResult: null });
    } catch (error) {
      console.error("GPX Upload Error:", error);
    }
  },

  runSimulation: async () => {
    const { gpxData, segments, riderProfile, _applySimulationStats } = get();
    if (!gpxData.length) return;
    try {
      const payload = { 
          points: gpxData, 
          segments: segments.map(s => ({ id: s.id, start_dist: s.start_dist, end_dist: s.end_dist, target_power: s.target_power })), 
          rider: riderProfile 
      };
      const response = await fetch('http://localhost:8123/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const result = await response.json();
      set({ segments: _applySimulationStats(segments, result), simulationResult: result });
    } catch (e) { console.error(e); }
  },

  exportGpx: () => { /* Same as before... */ },
  exportJson: () => { /* Same as before... */ },

  toggleSegmentSelection: (id, multi) => set(s => {
    const is = s.selectedSegmentIds.includes(id);
    if (multi && s.selectedSegmentIds.length) {
      const fIdx = s.segments.findIndex(x => x.id === s.selectedSegmentIds[0]);
      const lIdx = s.segments.findIndex(x => x.id === id);
      const range = s.segments.slice(Math.min(fIdx, lIdx), Math.max(fIdx, lIdx) + 1).map(x => x.id);
      return { selectedSegmentIds: range };
    }
    return { selectedSegmentIds: is ? (multi ? s.selectedSegmentIds.filter(x => x !== id) : []) : (multi ? [...s.selectedSegmentIds, id] : [id]) };
  }),

  splitSegment: (dist) => {
    const { segments, _getStatsForRange, _applySimulationStats } = get();
    const news = [];
    segments.forEach(seg => {
      if (dist > seg.start_dist && dist < seg.end_dist) {
        const s1 = _getStatsForRange(seg.start_dist, dist);
        const s2 = _getStatsForRange(dist, seg.end_dist);
        news.push({ ...seg, end_dist: dist, ...s1 });
        news.push({ ...seg, id: Date.now(), start_dist: dist, ...s2 });
      } else news.push(seg);
    });
    set({ segments: _applySimulationStats(news.sort((a, b) => a.start_dist - b.start_dist)) });
  },

  mergeSelectedSegments: () => set(s => {
    const targets = s.segments.filter(x => s.selectedSegmentIds.includes(x.id)).sort((a,b) => a.start_dist - b.start_dist);
    if (targets.length < 2) return s;
    const stats = s._getStatsForRange(targets[0].start_dist, targets[targets.length-1].end_dist);
    const merged = { ...targets[0], end_dist: targets[targets.length-1].end_dist, ...stats };
    const filtered = s.segments.filter(x => !s.selectedSegmentIds.includes(x.id));
    filtered.push(merged);
    return { segments: s._applySimulationStats(filtered.sort((a,b) => a.start_dist-b.start_dist)), selectedSegmentIds: [] };
  }),

  moveSegmentBoundary: (idx, dist) => set(s => {
    if (idx < 0 || idx >= s.segments.length - 1) return s;
    const s1 = { ...s.segments[idx], end_dist: dist };
    const s2 = { ...s.segments[idx+1], start_dist: dist };
    const st1 = s._getStatsForRange(s1.start_dist, s1.end_dist);
    const st2 = s._getStatsForRange(s2.start_dist, s2.end_dist);
    const news = [...s.segments]; news[idx] = { ...s1, ...st1 }; news[idx+1] = { ...s2, ...st2 };
    return { segments: s._applySimulationStats(news) };
  }),

  updateSegment: (id, u) => set(s => ({ segments: s.segments.map(seg => seg.id === id ? { ...seg, ...u } : seg) })),
}));

export default useCourseStore;
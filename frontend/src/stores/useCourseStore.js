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
      set({ gpxData: pointsWithGrade, atomicSegments: data.atomic_segments });

      // Initial Clustering (1 User Segment per Type change)
      const initialUserSegments = [];
      let currentGroup = [];
      
      data.atomic_segments.forEach((as, idx) => {
          const type = as.avg_grade > 3.5 ? 'UP' : (as.avg_grade < -3.5 ? 'DOWN' : 'FLAT');
          if (currentGroup.length === 0 || currentGroup[0].type === type) {
              currentGroup.push({ ...as, type });
          } else {
              // Commit Group
              const first = currentGroup[0];
              const last = currentGroup[currentGroup.length - 1];
              initialUserSegments.push({
                  id: initialUserSegments.length + 1,
                  start_dist: first.start_dist,
                  end_dist: last.end_dist,
                  type: first.type,
                  avg_grade: get()._getStatsForRange(first.start_dist, last.end_dist).avg_grade,
                  name: `Segment ${initialUserSegments.length + 1}`,
                  target_power: first.type === 'UP' ? 270 : 200
              });
              currentGroup = [{ ...as, type }];
          }
      });
      // Last one
      if (currentGroup.length > 0) {
          const first = currentGroup[0];
          const last = currentGroup[currentGroup.length - 1];
          initialUserSegments.push({
              id: initialUserSegments.length + 1,
              start_dist: first.start_dist,
              end_dist: last.end_dist,
              type: first.type,
              avg_grade: get()._getStatsForRange(first.start_dist, last.end_dist).avg_grade,
              name: `Segment ${initialUserSegments.length + 1}`,
              target_power: first.type === 'UP' ? 270 : 200
          });
      }

      set({ segments: initialUserSegments, simulationResult: null });
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
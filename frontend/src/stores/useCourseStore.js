import { create } from 'zustand';
import { XMLParser } from 'fast-xml-parser';

const useCourseStore = create((set, get) => ({
  gpxData: [], 
  segments: [], 
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

  _getGradeAndType: (startDist, endDist) => {
    const { gpxData } = get();
    if (!gpxData || gpxData.length === 0) return { type: 'FLAT', avg_grade: 0 };
    let startEle = gpxData[0].ele;
    let endEle = gpxData[gpxData.length-1].ele;
    for(const p of gpxData) { if (p.dist_m >= startDist) { startEle = p.ele; break; } }
    for(const p of gpxData) { if (p.dist_m >= endDist) { endEle = p.ele; break; } }
    const dist = endDist - startDist;
    const avgGrade = dist > 0 ? ((endEle - startEle) / dist) * 100 : 0;
    let type = 'FLAT';
    if (avgGrade > 3.5) type = 'UP';
    else if (avgGrade < -3.5) type = 'DOWN';
    return { type, avg_grade: avgGrade };
  },

  _applySimulationStats: (targetSegments, simData = null) => {
    const result = simData || get().simulationResult;
    if (!result || !result.track_data) return targetSegments;
    const track = result.track_data;
    return targetSegments.map(seg => {
      const relevantPoints = track.filter(p => (p.dist_km * 1000) > seg.start_dist && (p.dist_km * 1000) <= seg.end_dist);
      if (relevantPoints.length > 0) {
        const endTime = relevantPoints[relevantPoints.length - 1].time_sec;
        const prevPoint = track.findLast(p => (p.dist_km * 1000) <= seg.start_dist);
        const startTime = prevPoint ? prevPoint.time_sec : 0;
        const duration = endTime - startTime;
        const avgPower = relevantPoints.reduce((sum, p) => sum + p.power, 0) / relevantPoints.length;
        return { ...seg, simulated_duration: duration, simulated_avg_power: avgPower };
      }
      return seg;
    });
  },

  toggleSegmentSelection: (id, multiSelect) => set((state) => {
    const isSelected = state.selectedSegmentIds.includes(id);
    if (multiSelect && state.selectedSegmentIds.length > 0) {
      const firstId = state.selectedSegmentIds[0];
      const firstIdx = state.segments.findIndex(s => s.id === firstId);
      const lastIdx = state.segments.findIndex(s => s.id === id);
      if (firstIdx === -1 || lastIdx === -1) return state;
      const start = Math.min(firstIdx, lastIdx);
      const end = Math.max(firstIdx, lastIdx);
      return { selectedSegmentIds: state.segments.slice(start, end + 1).map(s => s.id) };
    } else {
      if (multiSelect) {
         return { selectedSegmentIds: isSelected ? state.selectedSegmentIds.filter(sid => sid !== id) : [...state.selectedSegmentIds, id] };
      } else {
         return { selectedSegmentIds: isSelected ? [] : [id] };
      }
    }
  }),

  loadGpxFromXml: (xmlString) => {
    const parser = new XMLParser({ ignoreAttributes: false });
    const jsonObj = parser.parse(xmlString);
    const trkpts = jsonObj?.gpx?.trk?.trkseg?.trkpt;
    if (!trkpts || !Array.isArray(trkpts)) return;
    const points = [];
    let totalDist = 0;
    const toRad = (deg) => (deg * Math.PI) / 180;
    const haversine = (p1, p2) => {
      const R = 6371000; 
      const dLat = toRad(p2.lat - p1.lat);
      const dLon = toRad(p2.lon - p1.lon);
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(toRad(p1.lat)) * Math.cos(toRad(p2.lat)) * Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    };
    let restoredState = null;
    try {
        const desc = jsonObj?.gpx?.trk?.desc;
        if (desc) restoredState = JSON.parse(desc.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>'));
    } catch (e) {}
    trkpts.forEach((pt, i) => {
      const lat = parseFloat(pt['@_lat']);
      const lon = parseFloat(pt['@_lon']);
      const ele = parseFloat(pt.ele || 0);
      let dist_m = 0;
      if (i > 0) {
        const stepDist = haversine(points[i-1], {lat, lon});
        totalDist += stepDist;
        dist_m = totalDist;
      }
      points.push({ lat, lon, ele, dist_m, grade_pct: i > 0 ? ((ele - points[i-1].ele) / (totalDist - points[i-1].dist_m)) * 100 : 0 });
    });
    if (restoredState && restoredState.segments) {
        set({ gpxData: points, segments: restoredState.segments, simulationResult: null });
        return;
    }
    let rawSegments = [];
    let startIdx = 0;
    for (let i = 1; i < points.length; i++) {
      const segDist = points[i].dist_m - points[startIdx].dist_m;
      const avgGrade = ((points[i].ele - points[startIdx].ele) / segDist) * 100;
      const gradeDelta = Math.abs(points[i].grade_pct - points[startIdx].grade_pct);
      if ((gradeDelta > 4.0 && segDist > 500) || i === points.length - 1) {
        let type = avgGrade > 3.5 ? 'UP' : (avgGrade < -3.5 ? 'DOWN' : 'FLAT');
        rawSegments.push({ start_dist: points[startIdx].dist_m, end_dist: points[i].dist_m, type, avg_grade: avgGrade });
        startIdx = i;
      }
    }
    const merged = [];
    if (rawSegments.length > 0) {
      let cur = rawSegments[0];
      for (let k = 1; k < rawSegments.length; k++) {
        if (cur.type === rawSegments[k].type) cur.end_dist = rawSegments[k].end_dist;
        else { merged.push(cur); cur = rawSegments[k]; }
      }
      merged.push(cur);
    }
    set({ gpxData: points });
    const final = merged.map((s, idx) => {
        const stats = get()._getGradeAndType(s.start_dist, s.end_dist);
        return { id: idx + 1, name: `Segment ${idx + 1}`, start_dist: s.start_dist, end_dist: s.end_dist, type: stats.type, avg_grade: stats.avg_grade, target_power: stats.type === "UP" ? get().riderProfile.ftp * 1.1 : get().riderProfile.ftp * 0.8 };
    });
    set({ segments: final, simulationResult: null });
  },

  runSimulation: async () => {
    const { gpxData, segments, riderProfile, _applySimulationStats } = get();
    if (!gpxData || gpxData.length === 0) return;
    try {
      const payload = { points: gpxData.map(p => ({ lat: p.lat, lon: p.lon, ele: p.ele, dist_m: p.dist_m })), segments: segments.map(s => ({ id: s.id, start_dist: s.start_dist, end_dist: s.end_dist, target_power: s.target_power })), rider: riderProfile };
      const response = await fetch('http://localhost:8123/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error('Simulation failed');
      const result = await response.json();
      set({ segments: _applySimulationStats(segments, result), simulationResult: result });
    } catch (error) { console.error("Simulation Error:", error); }
  },

  exportGpx: () => {
    const { gpxData, segments, riderProfile } = get();
    const metaData = JSON.stringify({ segments, riderProfile });
    let gpx = `<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="BikeCourseSimulator"><trk><name>Course Plan</name><desc>${metaData.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</desc><trkseg>`;
    gpxData.forEach(p => { gpx += `<trkpt lat="${p.lat}" lon="${p.lon}"><ele>${p.ele}</ele></trkpt>`; });
    gpx += `</trkseg></trk></gpx>`;
    const blob = new Blob([gpx], { type: 'application/gpx+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'course_plan.gpx'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
  },

  exportJson: () => {
    const { simulationResult } = get();
    if (!simulationResult) return;
    const blob = new Blob([JSON.stringify(simulationResult, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'simulation_result.json'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
  },

  splitSegment: (splitDist) => {
    const { segments, _getGradeAndType, _applySimulationStats } = get();
    const newSegments = [];
    segments.forEach(seg => {
      if (splitDist > seg.start_dist && splitDist < seg.end_dist) {
        const s1 = _getGradeAndType(seg.start_dist, splitDist);
        const s2 = _getGradeAndType(splitDist, seg.end_dist);
        newSegments.push({ ...seg, end_dist: splitDist, type: s1.type, avg_grade: s1.avg_grade });
        newSegments.push({ ...seg, id: Date.now(), start_dist: splitDist, type: s2.type, avg_grade: s2.avg_grade });
      } else newSegments.push(seg);
    });
    set({ segments: _applySimulationStats(newSegments.sort((a, b) => a.start_dist - b.start_dist)) });
  },

  mergeSelectedSegments: () => set((state) => {
    const { segments, selectedSegmentIds, _applySimulationStats, _getGradeAndType } = state;
    if (selectedSegmentIds.length < 2) return state;
    const targets = segments.filter(s => selectedSegmentIds.includes(s.id)).sort((a, b) => a.start_dist - b.start_dist);
    for (let i = 0; i < targets.length - 1; i++) { if (targets[i].end_dist !== targets[i+1].start_dist) return state; }
    const stats = _getGradeAndType(targets[0].start_dist, targets[targets.length-1].end_dist);
    const merged = { ...targets[0], end_dist: targets[targets.length-1].end_dist, type: stats.type, avg_grade: stats.avg_grade };
    const filtered = segments.filter(s => !selectedSegmentIds.includes(s.id));
    filtered.push(merged);
    return { segments: _applySimulationStats(filtered.sort((a, b) => a.start_dist - b.start_dist)), selectedSegmentIds: [] };
  }),

  moveSegmentBoundary: (idx, newDist) => set((state) => {
    if (idx < 0 || idx >= state.segments.length - 1) return state;
    const s1 = { ...state.segments[idx], end_dist: newDist };
    const s2 = { ...state.segments[idx+1], start_dist: newDist };
    const st1 = state._getGradeAndType(s1.start_dist, s1.end_dist);
    const st2 = state._getGradeAndType(s2.start_dist, s2.end_dist);
    const news = [...state.segments];
    news[idx] = { ...s1, type: st1.type, avg_grade: st1.avg_grade };
    news[idx+1] = { ...s2, type: st2.type, avg_grade: st2.avg_grade };
    return { segments: state._applySimulationStats(news) };
  }),

  updateRiderProfile: (p) => set((s) => ({ riderProfile: { ...s.riderProfile, ...p } })),
  updateSegment: (id, u) => set((s) => ({ segments: s.segments.map(seg => seg.id === id ? { ...seg, ...u } : seg) })),
}));

export default useCourseStore;

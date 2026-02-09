import { create } from 'zustand';
import { XMLParser } from 'fast-xml-parser';
import riderData from '../../../data/config/rider_data.json'; 

// --- Helper Functions (Pure Logic) ---
const calculateGradeAndType = (gpxData, startDist, endDist) => {
    if (!gpxData || gpxData.length === 0) return { type: 'FLAT', avg_grade: 0 };
    
    // Find elevation
    let startEle = gpxData[0].ele;
    let endEle = gpxData[gpxData.length-1].ele;
    
    // Simple find is robust enough
    for(const p of gpxData) { if (p.dist_m >= startDist) { startEle = p.ele; break; } }
    for(const p of gpxData) { if (p.dist_m >= endDist) { endEle = p.ele; break; } }

    const dist = endDist - startDist;
    const avgGrade = dist > 0 ? ((endEle - startEle) / dist) * 100 : 0;
    
    let type = 'FLAT';
    if (avgGrade > 3.5) type = 'UP';
    else if (avgGrade < -3.5) type = 'DOWN';
    
    return { type, avg_grade: avgGrade };
};

const initialRider = {
    ...riderData.rider_a,
    bike_weight: 8.5,
    cda: 0.32,
    crr: 0.005
};

const useCourseStore = create((set, get) => ({
  gpxData: [], 
  atomicSegments: [], 
  segments: [], 
  hoveredDist: null, 
  selectedSegmentIds: [], 
  simulationResult: null,
  riderProfile: initialRider,
  riderPresets: riderData,

  setHoveredDist: (dist) => set({ hoveredDist: dist }),

  applyRiderPreset: (key) => set((state) => {
    const preset = state.riderPresets[key];
    if (!preset) return state;
    return {
        riderProfile: {
            ...preset,
            pdc: { ...preset.pdc }, // Deep copy to protect preset data
            bike_weight: preset.bike_weight !== undefined ? preset.bike_weight : 8.5 
        }
    };
  }),

  updatePdcValue: (duration, power) => set((state) => {
    const newPdc = { ...state.riderProfile.pdc, [duration]: power };
    return { riderProfile: { ...state.riderProfile, pdc: newPdc } };
  }),

  deletePdcValue: (duration) => set((state) => {
    const newPdc = { ...state.riderProfile.pdc };
    delete newPdc[duration];
    return { riderProfile: { ...state.riderProfile, pdc: newPdc } };
  }),

  // Stats Aggregation (Needs Simulation Result)
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
        
        // Use helper to recalc grade
        const gpxData = get().gpxData;
        const stats = calculateGradeAndType(gpxData, seg.start_dist, seg.end_dist);
        
        const avgPower = relevantPoints.reduce((sum, p) => sum + p.power, 0) / relevantPoints.length;
        const avgSpeed = relevantPoints.reduce((sum, p) => sum + p.speed_kmh, 0) / relevantPoints.length;
        
        return { 
            ...seg, 
            simulated_duration: endTime - startTime, 
            simulated_avg_power: avgPower,
            simulated_avg_speed: avgSpeed,
            avg_grade: stats.avg_grade, // Ensure grade is correct
            type: stats.type
        };
      }
      return seg;
    });
  },

  toggleSegmentSelection: (id, multiSelect) => set((state) => {
    const isSelected = state.selectedSegmentIds.includes(id);
    if (multiSelect && state.selectedSegmentIds.length > 0) {
      const fIdx = state.segments.findIndex(s => s.id === state.selectedSegmentIds[0]);
      const lIdx = state.segments.findIndex(s => s.id === id);
      const range = state.segments.slice(Math.min(fIdx, lIdx), Math.max(fIdx, lIdx) + 1).map(s => s.id);
      return { selectedSegmentIds: range };
    }
    return { selectedSegmentIds: isSelected ? (multiSelect ? state.selectedSegmentIds.filter(x => x !== id) : []) : (multiSelect ? [...state.selectedSegmentIds, id] : [id]) };
  }),

  uploadGpx: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/upload_gpx', { method: 'POST', body: formData });
      if (!response.ok) throw new Error('Upload failed');
      const data = await response.json();

      // --- ADAPTER: Valhalla Standard JSON (Columnar) -> Frontend Objects (Row-based) ---
      
      const getBearing = (lat1, lon1, lat2, lon2) => {
          const rad = Math.PI / 180;
          lat1 *= rad; lon1 *= rad; lat2 *= rad; lon2 *= rad;
          const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
          const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
          return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
      };

      const shiftPoint = (lat, lon, bearing, dist) => {
          const R = 6378137;
          const rad = Math.PI / 180;
          const deg = 180 / Math.PI;
          lat *= rad; lon *= rad; bearing *= rad;
          const lat2 = Math.asin(Math.sin(lat) * Math.cos(dist / R) + Math.cos(lat) * Math.sin(dist / R) * Math.cos(bearing));
          const lon2 = lon + Math.atan2(Math.sin(bearing) * Math.sin(dist / R) * Math.cos(lat), Math.cos(dist / R) - Math.sin(lat) * Math.sin(lat2));
          return [lat2 * deg, lon2 * deg];
      };

      // 1. Parse Points & Calculate Shifted Visual Coordinates
      const pts = data.points;
      const count = pts.lat.length;
      const pointsWithGrade = [];
      const offset = 15.0; 

      for(let i=0; i<count; i++) {
          let bearing = 0;
          if (i === 0 && count > 1) {
              bearing = getBearing(pts.lat[i], pts.lon[i], pts.lat[i+1], pts.lon[i+1]) + 90;
          } else if (i === count - 1 && count > 1) {
              bearing = getBearing(pts.lat[i-1], pts.lon[i-1], pts.lat[i], pts.lon[i]) + 90;
          } else if (count > 2) {
              const b1 = getBearing(pts.lat[i-1], pts.lon[i-1], pts.lat[i], pts.lon[i]);
              const b2 = getBearing(pts.lat[i], pts.lon[i], pts.lat[i+1], pts.lon[i+1]);
              let avg = (b1 + b2) / 2;
              if (Math.abs(b1 - b2) > 180) avg += 180;
              bearing = avg + 90;
          }
          
          const [slat, slon] = shiftPoint(pts.lat[i], pts.lon[i], bearing, offset);

          pointsWithGrade.push({
              lat: pts.lat[i],
              lon: pts.lon[i],
              ele: pts.ele[i],
              dist_m: pts.dist[i],
              grade_pct: pts.grade[i] * 100,
              shifted_lat: slat,
              shifted_lon: slon
          });
      }

      // 2. Parse Atomic Segments
      const segs = data.segments;
      const atomicSegments = [];
      const segCount = segs.p_start.length;
      for(let i=0; i<segCount; i++) {
          const sIdx = segs.p_start[i];
          const eIdx = segs.p_end[i];
          
          if (sIdx >= count || eIdx >= count) continue;
          
          atomicSegments.push({
              start_dist: pts.dist[sIdx],
              end_dist: pts.dist[eIdx],
              avg_grade: segs.avg_grade[i] * 100,
              start_ele: pts.ele[sIdx],
              end_ele: pts.ele[eIdx],
              start_lat: pts.lat[sIdx],
              start_lon: pts.lon[sIdx],
              end_lat: pts.lat[eIdx],
              end_lon: pts.lon[eIdx],
              // Visualization coordinates
              shifted_start_lat: pointsWithGrade[sIdx].shifted_lat,
              shifted_start_lon: pointsWithGrade[sIdx].shifted_lon,
              shifted_end_lat: pointsWithGrade[eIdx].shifted_lat,
              shifted_end_lon: pointsWithGrade[eIdx].shifted_lon
          });
      }

      set({ gpxData: pointsWithGrade, atomicSegments: atomicSegments });
      
      const gpxDataForCalc = pointsWithGrade;

      let workSegments = atomicSegments.map(as => ({
          ...as,
          type: as.avg_grade > 3.5 ? 'UP' : (as.avg_grade < -3.5 ? 'DOWN' : 'FLAT'),
          length: as.end_dist - as.start_dist
      }));

      // Pass 1
      for (let i = 1; i < workSegments.length - 1; i++) {
          const prev = workSegments[i-1];
          const curr = workSegments[i];
          const next = workSegments[i+1];
          if (prev.type === next.type && curr.type !== prev.type) {
              if (curr.length < 500 && Math.abs(curr.avg_grade - prev.avg_grade) < 5.0) curr.type = prev.type;
          }
      }

      // Clustering
      const clusteredSegments = [];
      if (workSegments.length > 0) {
          let currentGroupStart = workSegments[0].start_dist;
          let currentType = workSegments[0].type;
          for (let i = 1; i < workSegments.length; i++) {
              const ws = workSegments[i];
              if (ws.type !== currentType) {
                  const prevEnd = workSegments[i-1].end_dist;
                  const stats = calculateGradeAndType(gpxDataForCalc, currentGroupStart, prevEnd);
                  clusteredSegments.push({
                      id: 0, start_dist: currentGroupStart, end_dist: prevEnd, type: currentType, avg_grade: stats.avg_grade
                  });
                  currentGroupStart = ws.start_dist;
                  currentType = ws.type;
              }
          }
          const lastEnd = workSegments[workSegments.length - 1].end_dist;
          const stats = calculateGradeAndType(gpxDataForCalc, currentGroupStart, lastEnd);
          clusteredSegments.push({
              id: 0, start_dist: currentGroupStart, end_dist: lastEnd, type: currentType, avg_grade: stats.avg_grade
          });
      }

      // Pass 2
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
              if (current.type === next.type || gradeDiff < 2.0 || isShort) {
                  current.end_dist = next.end_dist;
                  const stats = calculateGradeAndType(gpxDataForCalc, current.start_dist, current.end_dist);
                  current.avg_grade = stats.avg_grade;
                  current.type = stats.type;
                  changed = true;
              } else {
                  nextPass.push(current);
                  current = next;
              }
          }
          nextPass.push(current);
          mergedSegments = nextPass;
      }
      
      const finalUserSegments = mergedSegments.map((s, idx) => ({ ...s, id: idx + 1, name: `Segment ${idx + 1}` }));
      set({ segments: finalUserSegments, simulationResult: null });

    } catch (e) { console.error(e); }
  },

  runSimulation: async () => {
    const { gpxData, segments, riderProfile, _applySimulationStats } = get();
    if (!gpxData.length) return;
    try {
      const payload = { 
          points: gpxData, 
          segments: segments.map(s => ({ id: s.id, start_dist: s.start_dist, end_dist: s.end_dist })), 
          rider: {
              weight_kg: riderProfile.weight_kg,
              cp: riderProfile.cp,
              bike_weight: riderProfile.bike_weight,
              w_prime: riderProfile.w_prime,
              pdc: riderProfile.pdc
          }
      };
      const response = await fetch('/api/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const result = await response.json();
      set({ segments: _applySimulationStats(segments, result), simulationResult: result });
    } catch (e) { console.error(e); }
  },

  exportGpx: () => { 
    const { gpxData, segments, riderProfile } = get();
    const meta = JSON.stringify({ segments, riderProfile });
    let gpx = `<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="BikeCourseSimulator"><trk><name>Course Plan</name><desc>${meta.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</desc><trkseg>`;
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
    const { segments, riderProfile, _applySimulationStats, gpxData } = get();
    const news = [];
    segments.forEach(seg => {
      if (splitDist > seg.start_dist && splitDist < seg.end_dist) {
        const s1 = calculateGradeAndType(gpxData, seg.start_dist, splitDist);
        const s2 = calculateGradeAndType(gpxData, splitDist, seg.end_dist);
        news.push({ ...seg, end_dist: splitDist, ...s1 });
        news.push({ ...seg, id: Date.now(), start_dist: splitDist, ...s2 });
      } else news.push(seg);
    });
    set({ segments: _applySimulationStats(news.sort((a, b) => a.start_dist - b.start_dist)) });
  },

  mergeSelectedSegments: () => set(s => {
    const targets = s.segments.filter(x => s.selectedSegmentIds.includes(x.id)).sort((a,b) => a.start_dist - b.start_dist);
    if (targets.length < 2) return s;
    const stats = calculateGradeAndType(s.gpxData, targets[0].start_dist, targets[targets.length-1].end_dist);
    const merged = { ...targets[0], end_dist: targets[targets.length-1].end_dist, ...stats };
    const filtered = s.segments.filter(x => !s.selectedSegmentIds.includes(x.id));
    filtered.push(merged);
    return { segments: s._applySimulationStats(filtered.sort((a,b) => a.start_dist-b.start_dist)), selectedSegmentIds: [] };
  }),

  moveSegmentBoundary: (idx, dist) => set(s => {
    if (idx < 0 || idx >= s.segments.length - 1) return s;
    const s1 = { ...s.segments[idx], end_dist: dist };
    const s2 = { ...s.segments[idx+1], start_dist: dist };
    const st1 = calculateGradeAndType(s.gpxData, s1.start_dist, s1.end_dist);
    const st2 = calculateGradeAndType(s.gpxData, s2.start_dist, s2.end_dist);
    const news = [...s.segments]; news[idx] = { ...s1, ...st1 }; news[idx+1] = { ...s2, ...st2 };
    return { segments: s._applySimulationStats(news) };
  }),

  updateRiderProfile: (p) => set((s) => ({ riderProfile: { ...s.riderProfile, ...p } })),
  updateSegment: (id, u) => set((s) => ({ segments: s.segments.map(seg => seg.id === id ? { ...seg, ...u } : seg) })),
}));

export default useCourseStore;

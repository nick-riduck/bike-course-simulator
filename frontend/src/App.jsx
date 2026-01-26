import React from 'react'
import MapViewer from './components/MapViewer'
import ElevationChart from './components/ElevationChart'
import SegmentList from './components/SegmentList'
import useCourseStore from './stores/useCourseStore'

function App() {
  const { loadGpxFromXml, gpxData } = useCourseStore();

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      loadGpxFromXml(evt.target.result);
    };
    reader.readAsText(file);
  };

  return (
    <div className="min-h-screen bg-riduck-dark text-white p-4 md:p-8 flex flex-col items-center">
      <header className="w-full max-w-[1600px] mb-6 flex justify-between items-center">
        <h1 className="text-2xl font-bold text-riduck-primary flex items-center gap-2">
          🚵‍♂️ Riduck Simulator <span className="text-[10px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded font-normal uppercase tracking-widest">Alpha v2</span>
        </h1>
        <div className="flex gap-4 items-center">
          <label className="cursor-pointer bg-riduck-primary px-4 py-1.5 rounded-md font-bold hover:bg-opacity-80 transition-all text-xs">
            📁 Load GPX
            <input type="file" className="hidden" accept=".gpx" onChange={handleFileUpload} />
          </label>
          <div className="text-[10px] text-gray-500 font-mono">RIDUCK_USER_7267</div>
        </div>
      </header>
      
      <main className="w-full max-w-[1600px] grid grid-cols-1 lg:grid-cols-4 gap-6 h-[calc(100vh-160px)]">
        {/* Left Section: 3D Map & Elevation (Span 3) */}
        <div className="lg:col-span-3 flex flex-col gap-4 overflow-hidden">
          <div className="flex-1 min-h-0">
            <MapViewer />
          </div>
          <div className="h-fit">
            <ElevationChart />
          </div>
        </div>

        {/* Right Section: Segment List (Span 1) */}
        <div className="lg:col-span-1 h-full overflow-hidden">
          <SegmentList />
        </div>
      </main>
    </div>
  )
}

export default App;

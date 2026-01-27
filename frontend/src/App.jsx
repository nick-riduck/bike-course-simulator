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
      
      <main className="max-w-[1600px] mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6 p-6">
        {/* Left Side: Map & Chart (3/4 space) */}
        <div className="lg:col-span-8 xl:col-span-9 flex flex-col gap-6">
          <MapViewer />
          <ElevationChart />
        </div>

        {/* Right Side: Segment List (1/4 space) */}
        <div className="lg:col-span-4 xl:col-span-3 h-[900px]">
          <SegmentList />
        </div>
      </main>
    </div>
  )
}

export default App;

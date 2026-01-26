import React from 'react'
import MapViewer from './components/MapViewer'
import ElevationChart from './components/ElevationChart'
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
    <div className="min-h-screen bg-riduck-dark text-white p-4 md:p-10 flex flex-col items-center">
      <header className="w-full max-w-6xl mb-8 flex justify-between items-center">
        <h1 className="text-3xl md:text-4xl font-bold text-riduck-primary">
          Riduck Simulator <span className="text-xs text-gray-500 border border-gray-600 px-2 py-1 rounded ml-2">ALPHA</span>
        </h1>
        <div className="flex gap-4 items-center">
          <label className="cursor-pointer bg-riduck-primary px-4 py-2 rounded-lg font-bold hover:bg-opacity-80 transition-all text-sm">
            📁 Load GPX
            <input type="file" className="hidden" accept=".gpx" onChange={handleFileUpload} />
          </label>
          <div className="text-sm text-gray-400">User: 7267</div>
        </div>
      </header>
      
      <main className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: 3D Map & Elevation (Span 2) */}
        <div className="lg:col-span-2">
          <MapViewer />
          <ElevationChart />
          {gpxData.length > 0 && (
            <div className="mt-4 p-4 bg-riduck-card rounded-lg border border-gray-800 text-xs text-gray-400">
              Data Loaded: {gpxData.length} points | Total Distance: {(gpxData[gpxData.length-1].dist_m / 1000).toFixed(2)}km
            </div>
          )}
        </div>

        {/* Right Column: Controls & Info */}
        <div className="flex flex-col gap-4">
          {/* Legend Card */}
          <div className="p-5 bg-riduck-card rounded-xl border border-gray-800 shadow-lg">
            <h2 className="text-lg font-semibold mb-4 border-b border-gray-700 pb-2">Slope Legend</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm text-gray-300">
                  <div className="w-3 h-3 rounded-full bg-riduck-uphill"></div> Uphill (&gt;2%)
                </span>
                <span className="text-xs font-mono text-riduck-uphill">Challenge</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm text-gray-300">
                  <div className="w-3 h-3 rounded-full bg-riduck-flat"></div> Flat
                </span>
                <span className="text-xs font-mono text-riduck-flat">Cruising</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm text-gray-300">
                  <div className="w-3 h-3 rounded-full bg-riduck-downhill"></div> Downhill (&lt;-2%)
                </span>
                <span className="text-xs font-mono text-riduck-downhill">Speed</span>
              </div>
            </div>
          </div>

          {/* Simulation Control */}
          <div className="p-5 bg-riduck-card rounded-xl border border-gray-800 shadow-lg flex-1">
            <h2 className="text-lg font-semibold mb-4 text-riduck-primary">Simulation Control</h2>
            <p className="text-sm text-gray-400 mb-6">
              Upload a GPX file to start analyzing the course profile.
            </p>
            <button className="w-full py-3 bg-riduck-primary hover:bg-opacity-90 text-white font-bold rounded-lg transition-all shadow-md active:scale-95 disabled:bg-gray-700 disabled:text-gray-500 disabled:scale-100" 
                    disabled={gpxData.length === 0}>
              Run Simulation
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
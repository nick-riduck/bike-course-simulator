from __future__ import annotations

import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

class WeatherClient:
    """
    Client for Open-Meteo API to fetch historical or forecast weather data.
    Designed to work without an API key for the free tier.
    """
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    def __init__(self, use_scenario_mode: bool = False, scenario_data: Optional[Dict[str, float]] = None):
        """
        Initialize WeatherClient.
        
        Args:
            use_scenario_mode: If True, bypass API and use static scenario_data.
            scenario_data: Dict containing 'wind_speed', 'wind_deg', 'temperature'.
                           Required if use_scenario_mode is True.
        """
        self.use_scenario_mode = use_scenario_mode
        self.scenario_data = scenario_data or {}

    def get_weather(self, lat: float, lon: float, timestamp: datetime) -> Dict[str, float]:
        """
        Fetch weather data for a specific location and time.
        
        Args:
            lat: Latitude
            lon: Longitude
            timestamp: datetime object for the desired moment
            
        Returns:
            Dictionary with keys: 'wind_speed', 'wind_deg', 'temperature', 'pressure'
        """
        if self.use_scenario_mode:
            return self._get_scenario_weather()
            
        return self._fetch_from_api(lat, lon, timestamp)

    def _get_scenario_weather(self) -> Dict[str, float]:
        """Returns static scenario data."""
        return {
            "wind_speed": self.scenario_data.get("wind_speed", 0.0),
            "wind_deg": self.scenario_data.get("wind_deg", 0.0),
            "temperature": self.scenario_data.get("temperature", 20.0),
            "pressure": self.scenario_data.get("pressure", 1013.0)
        }

    def _fetch_from_api(self, lat: float, lon: float, timestamp: datetime) -> Dict[str, float]:
        """
        Internal method to call Open-Meteo API.
        
        Note: Open-Meteo requires start_date/end_date for historical data
        or hourly forecast access. We'll request a small window around the timestamp.
        """
        # Format date as YYYY-MM-DD
        date_str = timestamp.strftime("%Y-%m-%d")
        
        # Request parameters
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": date_str,
            "end_date": date_str,
            "hourly": "temperature_2m,surface_pressure,windspeed_10m,winddirection_10m",
            "timezone": "UTC" # Consistent timezone handling
        }
        
        query_string = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}?{query_string}"
        
        try:
            with urllib.request.urlopen(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP Error: {response.status}")
                
                data = json.loads(response.read().decode())
                return self._parse_api_response(data, timestamp)
                
        except Exception as e:
            print(f"[Warning] Weather API call failed: {e}. Using default values.")
            return {
                "wind_speed": 0.0,
                "wind_deg": 0.0,
                "temperature": 15.0,
                "pressure": 1013.0
            }

    def _parse_api_response(self, data: Dict[str, Any], target_time: datetime) -> Dict[str, float]:
        """
        Find the closest hourly data point to the target_time.
        """
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        
        if not times:
            return {"wind_speed": 0, "wind_deg": 0, "temperature": 15, "pressure": 1013}

        # Find index of the closest time
        # Open-Meteo returns time in ISO8601 "YYYY-MM-DDThh:mm"
        best_idx = 0
        min_diff = float('inf')
        
        target_ts = target_time.timestamp()
        
        for i, t_str in enumerate(times):
            # Parse time string (assuming UTC as requested)
            try:
                # Simple parsing for "2023-01-01T12:00" format
                dt = datetime.strptime(t_str, "%Y-%m-%dT%H:%M")
                # Assume basic UTC handling for simplicity in prototype
                diff = abs(dt.timestamp() - target_ts)
                
                if diff < min_diff:
                    min_diff = diff
                    best_idx = i
            except ValueError:
                continue

        # Extract values
        return {
            "temperature": hourly["temperature_2m"][best_idx],
            "pressure": hourly["surface_pressure"][best_idx],
            "wind_speed": hourly["windspeed_10m"][best_idx] / 3.6, # Convert km/h to m/s
            "wind_deg": hourly["winddirection_10m"][best_idx]
        }

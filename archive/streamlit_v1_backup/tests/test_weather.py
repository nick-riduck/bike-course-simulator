from src.weather_client import WeatherClient
from datetime import datetime

def test_weather():
    # 1. API 모드 테스트 (서울 시청)
    print("--- [Test 1] Open-Meteo API Fetch ---")
    client = WeatherClient()
    # 서울 시청 좌표, 오늘 오전 10시 기준 (UTC 가정)
    target_time = datetime.now()
    lat, lon = 37.5665, 126.9780
    
    result = client.get_weather(lat, lon, target_time)
    print(f"Location: Seoul ({lat}, {lon})")
    print(f"Result: {result}")
    
    assert "wind_speed" in result
    assert "wind_deg" in result
    print("API Fetch Success!\n")

    # 2. 시나리오 모드 테스트
    print("--- [Test 2] Scenario Mode ---")
    scenario_data = {
        "wind_speed": 5.5,
        "wind_deg": 270.0,
        "temperature": 25.0
    }
    scenario_client = WeatherClient(use_scenario_mode=True, scenario_data=scenario_data)
    s_result = scenario_client.get_weather(lat, lon, target_time)
    
    print(f"Expected: {scenario_data}")
    print(f"Result: {s_result}")
    
    assert s_result["wind_speed"] == 5.5
    assert s_result["wind_deg"] == 270.0
    print("Scenario Mode Success!")

if __name__ == "__main__":
    test_weather()

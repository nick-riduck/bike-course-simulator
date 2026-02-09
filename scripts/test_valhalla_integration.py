import sys
import os
import json
import httpx

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.valhalla import ValhallaClient

def test_valhalla():
    # 1. Initialize Client
    client = ValhallaClient()
    print(f"Testing Valhalla at: {client.url}")
    
    # 2. Sample points (Seoul Station -> Namyeong Area)
    # 확실히 큰 도로 위에 있는 좌표로 테스트
    sample_points = [
        {"lat": 37.5536, "lon": 126.9726},
        {"lat": 37.5501, "lon": 126.9724},
        {"lat": 37.5472, "lon": 126.9718}
    ]
    
    try:
        # 3. Call Valhalla & Parse
        print("Sending request to Valhalla...")
        
        # Raw Response 확인을 위해 직접 호출 로직 추가
        with httpx.Client() as c:
            # 1. Test Trace Attributes
            trace_payload = {
                "shape": sample_points,
                "costing": "bicycle",
                "shape_match": "map_snap"
            }
            raw_resp = c.post(f"{client.url}/trace_attributes", json=trace_payload)
            print(f"Trace Status: {raw_resp.status_code}")
            
            # 2. Test Height API
            height_payload = {
                "shape": sample_points,
                "range": False
            }
            h_resp = c.post(f"{client.url}/height", json=height_payload)
            print(f"Height Status: {h_resp.status_code}")
            if h_resp.status_code == 200:
                print(f"Height Response: {h_resp.json()}")
            else:
                print(f"Height Error: {h_resp.text}")
            
        result = client.get_standard_course(sample_points)
        
        # 4. Verify Structure
        print("\n[SUCCESS] Received Standard JSON v1.0")
        print(f"Stats: {result['stats']}")
        print(f"Points Count: {len(result['points']['lat'])}")
        print(f"Segments Count: {len(result['segments']['p_start'])}")
        
        # 5. Check first few points & segments
        print("\nFirst Segment Data:")
        for key in result['segments']:
            print(f"  {key}: {result['segments'][key][0]}")
            
        # 6. Save for inspection
        output_file = "data/output/valhalla_test_result.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nFull result saved to {output_file}")
        
    except Exception as e:
        print(f"\n[FAILED] {str(e)}")
        print("Is Valhalla running at localhost:8002?")

if __name__ == "__main__":
    test_valhalla()

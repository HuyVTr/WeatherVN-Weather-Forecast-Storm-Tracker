import math
import numpy as np

# ============================================================
# 2. ORIGIN DETECTION MODULE
# ============================================================

class StormOriginDetector:
    FORMATION_ZONES = {
        'south_china_sea': {
            'name': 'Biển Đông',
            'bounds': {'LAT': (0, 25), 'LON': (100, 121)},
            'risk_level': 'HIGH',
            'typical_direction': 'NW'
        },
        'western_pacific': {
            'name': 'Tây Thái Bình Dương',
            'bounds': {'LAT': (5, 20), 'LON': (121, 160)},
            'risk_level': 'VERY_HIGH',
            'typical_direction': 'W-NW'
        },
        'philippine_sea': {
            'name': 'Biển Philippines',
            'bounds': {'LAT': (10, 25), 'LON': (120, 135)},
            'risk_level': 'HIGH',
            'typical_direction': 'WNW'
        }
    }
    
    @staticmethod
    def detect_origin(lat, lon):
        for zone_key, zone_info in StormOriginDetector.FORMATION_ZONES.items():
            bounds = zone_info['bounds']
            if (bounds['LAT'][0] <= lat <= bounds['LAT'][1] and 
                bounds['LON'][0] <= lon <= bounds['LON'][1]):
                return {
                    'zone': zone_key,
                    'zone_name': zone_info['name'],
                    'risk_level': zone_info['risk_level'],
                    'typical_direction': zone_info['typical_direction'],
                    'coordinates': {'LAT': lat, 'LON': lon}
                }
        return {
            'zone': 'unknown',
            'zone_name': 'Vùng khác',
            'risk_level': 'UNKNOWN',
            'typical_direction': 'Unknown',
            'coordinates': {'LAT': lat, 'LON': lon}
        }


# ============================================================
# 3. TRAJECTORY ANALYZER
# ============================================================

class TrajectoryAnalyzer:
    @staticmethod
    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return 2 * R * math.asin(math.sqrt(a))
    
    @staticmethod
    def compute_bearing(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.atan2(x, y)
        return (math.degrees(bearing) + 360) % 360
    
    @staticmethod
    def bearing_to_direction(bearing):
        if np.isnan(bearing):
            return 'Unknown'
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                      'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        idx = int((bearing + 11.25) / 22.5) % 16
        return directions[idx]
    
    @staticmethod
    def analyze_trajectory(predictions):
        if len(predictions) < 2:
            # Return a default structure instead of None to avoid frontend errors
            return {
                'total_distance_km': 0,
                'avg_speed_kmh': 0,
                'dominant_direction': 'Unknown',
                'dominant_bearing': 0,
                'path_changes': [],
                'enters_scs': False,
                'scs_entry_point': None,
                'threatens_vietnam': False
            }
        
        analysis = {
            'total_distance': 0,
            'avg_speed': 0,
            'dominant_direction': None,
            'dominant_bearing': 0,
            'path_changes': [],
            'enters_scs': False,
            'scs_entry_point': None,
            'threatens_vietnam': False
        }
        
        bearings = []
        speeds = []
        
        for i in range(1, len(predictions)):
            try:
                prev = predictions[i-1]
                curr = predictions[i]

                # Ensure the required keys exist and are not None
                if 'LAT' not in prev or 'LON' not in prev or 'LAT' not in curr or 'LON' not in curr or \
                   prev['LAT'] is None or prev['LON'] is None or curr['LAT'] is None or curr['LON'] is None:
                    continue

                dist = TrajectoryAnalyzer.haversine_distance(
                    prev['LAT'], prev['LON'], curr['LAT'], curr['LON']
                )
                analysis['total_distance'] += dist
                speeds.append(dist) # speed in km/h since time step is 1 hour
                
                bearing = TrajectoryAnalyzer.compute_bearing(
                    prev['LAT'], prev['LON'], curr['LAT'], curr['LON']
                )
                bearings.append(bearing)
                
                if len(bearings) > 1:
                    bearing_change = abs(bearings[-1] - bearings[-2])
                    if bearing_change > 180:
                        bearing_change = 360 - bearing_change
                    if bearing_change > 45:
                        if curr.get('hour'): # Ensure hour key exists
                            analysis['path_changes'].append({
                                'hour': curr['hour'],
                                'from_bearing': bearings[-2],
                                'to_bearing': bearings[-1],
                                'location': {'LAT': curr['LAT'], 'LON': curr['LON']},
                                'change_degrees': bearing_change
                            })
                
                scs_bounds = StormOriginDetector.FORMATION_ZONES['south_china_sea']['bounds']
                if (scs_bounds['LAT'][0] <= curr['LAT'] <= scs_bounds['LAT'][1] and 
                    scs_bounds['LON'][0] <= curr['LON'] <= scs_bounds['LON'][1]):
                    if not analysis['enters_scs'] and curr.get('hour'):
                        analysis['enters_scs'] = True
                        analysis['scs_entry_point'] = {
                            'hour': curr['hour'],
                            'LAT': curr['LAT'],
                            'LON': curr['LON']
                        }
                
                vietnam_coords = [
                    ('Da Nang', 16.07, 108.22), 
                    ('Hai Phong', 20.84, 106.68), 
                    ('Ho Chi Minh City', 10.82, 106.63)
                ]
                for city, city_lat, city_lon in vietnam_coords:
                    dist_to_vn = TrajectoryAnalyzer.haversine_distance(
                        curr['LAT'], curr['LON'], city_lat, city_lon
                    )
                    if dist_to_vn < 500: # 500km threshold
                        analysis['threatens_vietnam'] = True
                        break
            except Exception as e:
                print(f"Skipping a point in trajectory analysis due to error: {e}")
                continue
        
        mean_bearing = np.mean(bearings) if bearings else 0
        analysis['dominant_bearing'] = mean_bearing
        analysis['avg_speed_kmh'] = np.mean(speeds) if speeds else 0
        analysis['dominant_direction'] = TrajectoryAnalyzer.bearing_to_direction(
            mean_bearing
        ) if bearings else 'Unknown'
        
        # Rename for frontend compatibility
        analysis['total_distance_km'] = analysis.pop('total_distance')
        analysis.pop('avg_speed', None) # Remove old key if it exists

        return analysis

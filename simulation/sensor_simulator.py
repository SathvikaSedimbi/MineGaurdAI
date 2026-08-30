import math
import random

class SensorSimulator:
    @staticmethod
    def generate_sensor_detections(vehicle, other_vehicles, workers, weather_state, visibility_m):
        """
        Simulates individual raw target returns for RGB Camera, Thermal Camera, and Radar
        mounted on the vehicle, based on proximity, heading, and weather degradation.
        """
        vx = vehicle["position"]["x"]
        vy = vehicle["position"]["y"]
        v_id = vehicle["id"]
        v_heading = vehicle.get("heading", 0.0)
        
        # Sensor hardware health levels (0.0 to 1.0)
        healths = vehicle.get("sensor_health", {"rgb": 1.0, "thermal": 1.0, "radar": 1.0})
        
        rgb_detections = []
        thermal_detections = []
        radar_detections = []
        
        # Max sensing range is 80 meters
        max_range = 80.0
        
        # Compile list of potential targets (other vehicles and workers)
        targets = []
        for other in other_vehicles:
            if other["id"] != v_id:
                targets.append({
                    "id": other["id"],
                    "type": "Vehicle",
                    "x": other["position"]["x"],
                    "y": other["position"]["y"],
                    "speed_mps": other["speed_kmh"] / 3.6
                })
                
        for worker in workers:
            targets.append({
                "id": worker["id"],
                "type": "Person",
                "x": worker["position"]["x"],
                "y": worker["position"]["y"],
                "speed_mps": worker.get("speed_mps", 0.8)
            })
            
        # Add a static mock obstacle (e.g., boulder or road edge hazard) on certain roads for realism
        if vehicle.get("current_road") == "H-07":
            # Add a boulder target on H-07 ramp
            targets.append({
                "id": "OBS-BOULDER",
                "type": "Obstacle",
                "x": 665,
                "y": 180,
                "speed_mps": 0.0
            })
            
        for t in targets:
            dx = t["x"] - vx
            dy = t["y"] - vy
            dist = math.sqrt(dx*dx + dy*dy)
            
            # Skip if out of physical maximum range
            if dist > max_range:
                continue
                
            # Filter by sensor field-of-view (FOV) cone of 90 degrees (+/- 45 degrees in direction of travel)
            target_angle_rad = math.atan2(dy, dx)
            target_angle_deg = math.degrees(target_angle_rad)
            
            angle_diff = (target_angle_deg - v_heading + 180) % 360 - 180
            if abs(angle_diff) > 75: # Slightly wider to allow side warnings
                continue
                
            # --- 1. RGB CAMERA SIMULATION ---
            # RGB camera visibility is strictly bound to weather visibility range
            rgb_health = healths.get("rgb", 1.0)
            if rgb_health > 0.15:
                # If target is within weather visibility limit, camera can see it
                if dist <= visibility_m:
                    # Confidence decays with distance and fog/dust density
                    vis_factor = dist / max(1.0, visibility_m)
                    base_conf = 0.95 - (vis_factor * 0.4)
                    # Apply health
                    rgb_conf = max(0.1, base_conf) * rgb_health
                    
                    rgb_detections.append({
                        "id": t["id"],
                        "type": t["type"],
                        "distance": dist,
                        "confidence": round(rgb_conf, 2)
                    })
                elif dist <= visibility_m * 1.5:
                    # Weak shadow outline detection
                    rgb_conf = 0.25 * rgb_health
                    rgb_detections.append({
                        "id": t["id"],
                        "type": "Obstacle", # Can't resolve type clearly in haze
                        "distance": dist,
                        "confidence": round(rgb_conf, 2)
                    })
                    
            # --- 2. THERMAL CAMERA SIMULATION ---
            # Thermal sees heat signatures. Resilient to fog, but heavy rain masks thermal energy.
            thermal_health = healths.get("thermal", 1.0)
            if thermal_health > 0.15:
                rain = weather_state.get("rain", 0.0)
                fog = weather_state.get("fog", 0.0)
                
                # Rain water layer absorbs thermal radiation, fog scatters it slightly
                thermal_attenuation = (rain * 0.0035) + (fog * 0.001)
                thermal_range_limit = max_range * (1.0 - thermal_attenuation)
                
                if dist <= thermal_range_limit:
                    # Thermal resolves human body heat or warm truck engine
                    base_conf = 0.92 - (dist / thermal_range_limit) * 0.25
                    # Person has a stronger thermal profile than a wet dumper in heavy rain
                    if t["type"] == "Person":
                        base_conf += 0.05
                    thermal_conf = max(0.15, min(0.99, base_conf)) * thermal_health
                    
                    thermal_detections.append({
                        "id": t["id"],
                        "type": t["type"],
                        "distance": dist,
                        "confidence": round(thermal_conf, 2)
                    })
                    
            # --- 3. RADAR SIMULATION ---
            # Radar is highly resilient to atmospheric dust, fog, and light rain.
            radar_health = healths.get("radar", 1.0)
            if radar_health > 0.15:
                # Heavy rain scatters radar frequency slightly (reduces max range by 10-15%)
                rain = weather_state.get("rain", 0.0)
                radar_range_limit = max_range * (1.0 - 0.0015 * rain)
                
                if dist <= radar_range_limit:
                    # Radar gets distance and relative velocity but poor classification (usually returns generic Obstacle)
                    base_conf = 0.96 - (dist / radar_range_limit) * 0.1
                    radar_conf = max(0.30, base_conf) * radar_health
                    
                    # Radar calculates closing speed directly using Doppler effect
                    rel_speed = t["speed_mps"] - (vehicle["speed_kmh"] / 3.6)
                    
                    radar_detections.append({
                        "id": t["id"],
                        "type": "Obstacle",
                        "distance": dist,
                        "confidence": round(radar_conf, 2),
                        "relative_speed": round(rel_speed, 1)
                    })
                    
        return rgb_detections, thermal_detections, radar_detections

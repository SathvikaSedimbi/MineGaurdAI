class AlertEngine:
    @staticmethod
    def generate_alerts(vehicles, workers, weather, roads, active_conflicts):
        """
        Scans fleet and environment state to produce explainable prioritized alerts.
        """
        alerts = []
        
        # 1. Check active vehicle-to-vehicle conflicts (TTC / Collision)
        for conflict in active_conflicts:
            v1_id = conflict["v1"]
            v2_id = conflict["v2"]
            ttc = conflict["ttc"]
            dist = conflict["distance"]
            road = conflict.get("road_id", "Unknown Road")
            
            # Find vehicle names
            v1_name = next((v["name"] for v in vehicles if v["id"] == v1_id), v1_id)
            v2_name = next((v["name"] for v in vehicles if v["id"] == v2_id), v2_id)
            
            v1 = next((v for v in vehicles if v["id"] == v1_id), None)
            
            # Generate Explainability string
            explanation = (
                f"Collision predicted between {v1_name} and {v2_name} on {road}. "
                f"TTC is {ttc}s at a distance of {dist}m. "
            )
            if weather.get("fog", 0.0) >= 70.0:
                explanation += f"Thick fog ({weather['fog']}%) has reduced operator visual field to {weather.get('visibility', 10.0)}m. "
            if v1 and v1.get("speed_kmh", 0.0) > v1.get("recommended_speed_kmh", 30.0):
                explanation += f"{v1_name} speed ({v1['speed_kmh']} km/h) exceeds safe recommended speed ({v1['recommended_speed_kmh']} km/h) for current road."
                
            alerts.append({
                "id": f"ALT-COL-{v1_id}-{v2_id}",
                "level": "CRITICAL",
                "title": f"Collision Imminent: {v1_id} ↔ {v2_id}",
                "source": v1_id,
                "timestamp": None,  # Will be filled by Flask app time
                "explanation": explanation,
                "action": f"{v1_id} REDUCE SPEED IMMEDIATELY | {v2_id} HOLD POSITION"
            })
            
        # 2. Check Worker proximity alerts
        for vehicle in vehicles:
            v_id = vehicle["id"]
            for worker in workers:
                w_id = worker["id"]
                # Calculate distance
                xv, yv = vehicle["position"]["x"], vehicle["position"]["y"]
                xw, yw = worker["position"]["x"], worker["position"]["y"]
                dist = ((xv - xw)**2 + (yv - yw)**2)**0.5
                
                # Scale: 1 pixel = 1 meter. Trigger warning if within 40m.
                if dist < 40.0:
                    level = "CRITICAL" if dist < 18.0 else "HIGH"
                    rgb_conf = vehicle.get("sensor_confidence", {}).get("rgb", 1.0)
                    thermal_conf = vehicle.get("sensor_confidence", {}).get("thermal", 1.0)
                    
                    explanation = (
                        f"Worker {worker['name']} ({worker['designation']}) is in close proximity ({round(dist, 1)}m) "
                        f"to vehicle {vehicle['name']}. "
                    )
                    
                    if rgb_conf < 0.30 and thermal_conf > 0.60:
                        explanation += "RGB visibility is blocked. Worker detected via Thermal Camera heat signature."
                    elif rgb_conf < 0.30 and thermal_conf < 0.40:
                        explanation += "Camera systems severely degraded. Detection relies on active vehicle RADAR."
                    else:
                        explanation += "Visual contact established by multi-sensor fusion."
                        
                    alerts.append({
                        "id": f"ALT-WRK-{v_id}-{w_id}",
                        "level": level,
                        "title": f"Worker Proximity: {worker['name']} ({w_id})",
                        "source": v_id,
                        "explanation": explanation,
                        "action": f"{v_id} SLOW DOWN TO 10 km/h | SOUND HORN"
                    })
                    
        # 3. Check Road degradation & blockages alerts
        for road in roads:
            if road.get("is_blocked"):
                alerts.append({
                    "id": f"ALT-ROAD-BLK-{road['id']}",
                    "level": "CRITICAL",
                    "title": f"Road Blocked: {road['id']}",
                    "source": "ROAD_ENGINE",
                    "explanation": f"Haul Road {road['name']} ({road['id']}) is BLOCKED due to an active landslide, flooding, or calamity.",
                    "action": "AVOID SEGMENT | REROUTE NOW"
                })
            elif road["is_restricted"]:
                alerts.append({
                    "id": f"ALT-ROAD-RST-{road['id']}",
                    "level": "HIGH",
                    "title": f"Road Restricted: {road['name']} ({road['id']})",
                    "source": "ROAD_ENGINE",
                    "explanation": f"Haul Road {road['id']} has been closed due to severe physical hazards or construction safety violations.",
                    "action": "REROUTE ALL APPROACHING FLEET VEHICLES"
                })
            elif road["potholes"] >= 6 or road["water_accumulation"] >= 0.70:
                potholes = road["potholes"]
                water = int(road["water_accumulation"] * 100)
                
                explanation = (
                    f"Road {road['name']} ({road['id']}) surface is highly degraded. "
                    f"Potholes: {potholes}, Water Accumulation: {water}%. "
                    f"Friction coefficient reduced by heavy rainfall accumulation."
                )
                
                alerts.append({
                    "id": f"ALT-ROAD-DEG-{road['id']}",
                    "level": "MEDIUM",
                    "title": f"Road Degraded: {road['id']}",
                    "source": "ROAD_ENGINE",
                    "explanation": explanation,
                    "action": f"REDUCE SPEED TO {road['recommended_speed']} km/h"
                })
                
        # 4. Check Sensor health degradation alerts
        for vehicle in vehicles:
            v_id = vehicle["id"]
            healths = vehicle.get("sensor_health", {})
            for sensor, health in healths.items():
                if health <= 0.20:
                    explanation = (
                        f"Vehicle {vehicle['name']} {sensor.upper()} hardware reporting critical degradation ({int(health*100)}% health). "
                        f"Likely causes: physical vibration fault, mud occlusion, lens fogging, or electrical damage. "
                        f"Fusion algorithm has re-weighted tracking parameters to compensate."
                    )
                    
                    all_failed = all(h <= 0.20 for h in healths.values())
                    level = "CRITICAL" if all_failed else "LOW"
                    action = "SCHEDULE IMMEDIATE CONTROLLED VEHICLE STOP" if all_failed else "DISPATCH CLEANING / SENSOR CALIBRATION UNIT"
                    
                    alerts.append({
                        "id": f"ALT-SNS-{v_id}-{sensor}",
                        "level": level,
                        "title": f"Sensor Failure: {v_id} {sensor.upper()}",
                        "source": v_id,
                        "explanation": explanation,
                        "action": action
                    })

        # 5. Check Vehicle blockages and Emergency statuses
        for vehicle in vehicles:
            v_id = vehicle["id"]
            
            # Emergency status active alert
            if vehicle.get("priority") == "EMERGENCY" and vehicle.get("status") == "ACTIVE":
                alerts.append({
                    "id": f"ALT-EM-ACTIVE-{v_id}",
                    "level": "CRITICAL",
                    "title": f"EMERGENCY PRIORITY ACTIVE: {v_id}",
                    "source": v_id,
                    "explanation": f"Emergency vehicle {vehicle['name']} ({v_id}) is active. Digital-twin V2V prioritized right-of-way activated.",
                    "action": "YIELD RIGHT-OF-WAY | SLOW DOWN / HOLD"
                })
                
            # Blockage warnings
            alert_status = vehicle.get("alertStatus")
            if alert_status == "REROUTING":
                alerts.append({
                    "id": f"ALT-VEH-REROUTE-{v_id}",
                    "level": "HIGH",
                    "title": f"Rerouting Fleet: {v_id}",
                    "source": v_id,
                    "explanation": f"Vehicle {v_id} route recalculated successfully due to a blockage ahead.",
                    "action": "FOLLOW ALTERNATIVE ROUTE"
                })
            elif alert_status == "STOPPED_NO_ROUTE":
                alerts.append({
                    "id": f"ALT-VEH-STOP-{v_id}",
                    "level": "CRITICAL",
                    "title": f"STOPPED (NO ROUTE): {v_id}",
                    "source": v_id,
                    "explanation": f"Vehicle {v_id} is unable to find a safe alternate route. Stopped at a safe location.",
                    "action": "HOLD POSITION | WAIT FOR CLEARANCE"
                })
            elif alert_status == "STOPPED_NEAR_BLOCKAGE":
                alerts.append({
                    "id": f"ALT-VEH-HAZ-{v_id}",
                    "level": "CRITICAL",
                    "title": f"IMMEDIATE STOP ORDER: {v_id}",
                    "source": v_id,
                    "explanation": f"Vehicle {v_id} is in close proximity to an active road blockage. Stopped to prevent calamity.",
                    "action": "HOLD POSITION"
                })
                
        return alerts

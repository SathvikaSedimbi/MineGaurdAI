import os
import json
import time
import math
import threading
from flask import Flask, jsonify, render_template, request

# Import core analytical engines
from core.weather_engine import WeatherEngine
from core.visibility_engine import VisibilityEngine
from core.sensor_fusion import SensorFusion
from core.road_health import RoadHealth
from core.collision_engine import CollisionEngine
from core.risk_engine import RiskEngine
from core.alert_engine import AlertEngine
from core.route_engine import RouteEngine

# Import simulators
from simulation.vehicle_simulator import VehicleSimulator
from simulation.worker_simulator import WorkerSimulator
from simulation.weather_simulator import WeatherSimulator
from simulation.sensor_simulator import SensorSimulator
from simulation.road_simulator import RoadSimulator
from simulation.scenario_engine import ScenarioEngine

app = Flask(__name__)

# State lock for thread-safe state mutations
state_lock = threading.Lock()

# Global State Container
sim_state = {
    "nodes": [],
    "roads": [],
    "vehicles": [],
    "workers": [],
    "weather": {},
    "target_weather": {},
    "visibility_m": 120.0,
    "visibility_category": "CLEAR",
    "active_road_scan": None,
    "active_conflicts": [],
    "alerts": [],
    "simulation_time": 0.0,
    "simulation_running": True,
    "scenarios_config": [],
    "incidents": [],
    "timeline": [],
    "fleet_notifications": {
        "sent": 0,
        "delivered": 0,
        "acknowledged": 0,
        "pending": 0
    },
    "analytics_history": {
        "time": [],
        "visibility": [],
        "alerts_count": [],
        "avg_speed": [],
        "risk_distribution": {"NORMAL": 5, "CAUTION": 0, "HIGH_RISK": 0, "CRITICAL": 0}
    }
}

# Instantiate Engines
weather_engine = WeatherEngine()
scenario_engine = ScenarioEngine()

def load_initial_data():
    """Loads default JSON configurations into state memory."""
    global sim_state
    
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    
    with open(os.path.join(data_dir, "mine_map.json"), "r") as f:
        map_data = json.load(f)
        sim_state["nodes"] = map_data["nodes"]
        sim_state["benches"] = map_data["benches"]
        sim_state["restricted_zones"] = map_data["restricted_zones"]
        
    with open(os.path.join(data_dir, "roads.json"), "r") as f:
        sim_state["roads"] = json.load(f)
        
    with open(os.path.join(data_dir, "vehicles.json"), "r") as f:
        sim_state["vehicles"] = json.load(f)
        
    with open(os.path.join(data_dir, "workers.json"), "r") as f:
        sim_state["workers"] = json.load(f)
        
    with open(os.path.join(data_dir, "scenarios.json"), "r") as f:
        sim_state["scenarios_config"] = json.load(f)
        
    with open(os.path.join(data_dir, "weather_profiles.json"), "r") as f:
        sim_state["weather_profiles"] = json.load(f)
        
    # Set default weather to Clear
    clear_profile = sim_state["weather_profiles"]["clear"]
    sim_state["weather"] = {k: v for k, v in clear_profile.items() if k != "name" and k != "visibility"}
    sim_state["target_weather"] = dict(sim_state["weather"])
    sim_state["visibility_m"] = clear_profile["visibility"]
    sim_state["visibility_category"] = "CLEAR"
    
    sim_state["simulation_time"] = 0.0
    sim_state["active_road_scan"] = None
    sim_state["active_conflicts"] = []
    sim_state["alerts"] = []
    sim_state["trigger_reroute_v3"] = False
    
    sim_state["incidents"] = []
    sim_state["timeline"] = [
        {"time": "00:00:00", "message": "MineGuard Safety System Initialized."}
    ]
    sim_state["fleet_notifications"] = {
        "sent": 0,
        "delivered": 0,
        "acknowledged": 0,
        "pending": 0
    }
    
    # Reset history
    sim_state["analytics_history"] = {
        "time": [0],
        "visibility": [clear_profile["visibility"]],
        "alerts_count": [0],
        "avg_speed": [28.0],
        "risk_distribution": {"NORMAL": 5, "CAUTION": 0, "HIGH_RISK": 0, "CRITICAL": 0}
    }
    
    scenario_engine.reset_scenario()

# Initial load
load_initial_data()

def get_relative_direction(heading, dx, dy):
    target_angle = math.degrees(math.atan2(dy, dx))
    rel_angle = (target_angle - heading + 180) % 360 - 180
    if -22.5 <= rel_angle < 22.5:
        return "Front"
    elif 22.5 <= rel_angle < 67.5:
        return "Front-right"
    elif 67.5 <= rel_angle < 112.5:
        return "Right"
    elif 112.5 <= rel_angle < 157.5:
        return "Rear-right"
    elif 157.5 <= rel_angle <= 180 or -180 <= rel_angle < -157.5:
        return "Rear"
    elif -157.5 <= rel_angle < -112.5:
        return "Rear-left"
    elif -112.5 <= rel_angle < -67.5:
        return "Left"
    else:
        return "Front-left"

def get_distance_to_blockage(vehicle, roads, nodes):
    route = vehicle.get("route", [])
    route_idx = vehicle.get("route_index", 0)
    if not route or route_idx >= len(route) - 1:
        return 9999.0, None
        
    blocked_road_id = None
    blocked_idx = -1
    for i in range(route_idx, len(route) - 1):
        node_u = route[i]
        node_v = route[i+1]
        
        connecting_road = next((r for r in roads if r.get("is_blocked") and 
                                ((r["start_node"] == node_u and r["end_node"] == node_v) or 
                                 (r["start_node"] == node_v and r["end_node"] == node_u))), None)
        if connecting_road:
            blocked_road_id = connecting_road["id"]
            blocked_idx = i
            break
            
    if blocked_idx == -1:
        return 9999.0, None
        
    next_node_id = route[route_idx + 1]
    next_node = next((n for n in nodes if n["id"] == next_node_id), None)
    if not next_node:
        return 9999.0, None
        
    vx, vy = vehicle["position"]["x"], vehicle["position"]["y"]
    dist = math.sqrt((next_node["x"] - vx)**2 + (next_node["y"] - vy)**2)
    
    for i in range(route_idx + 1, blocked_idx):
        if i >= len(route) - 1:
            break
        u = route[i]
        v = route[i+1]
        road = next((r for r in roads if (r["start_node"] == u and r["end_node"] == v) or 
                                          (r["start_node"] == v and r["end_node"] == u)), None)
        if road:
            dist += road["length_m"]
            
    return dist, blocked_road_id

def tick_simulation(dt=0.5):
    """Primary simulation clock cycle, executed twice per second (2Hz)."""
    global sim_state
    
    with state_lock:
        if not sim_state["simulation_running"]:
            return
            
        # 1. Step Scenario Timeline
        if scenario_engine.scenario_active:
            scenario_engine.step_scenario(sim_state, dt)
            
        # 2. Interpolate Environmental/Weather Transition
        curr_weather = sim_state["weather"]
        targ_weather = sim_state["target_weather"]
        sim_state["weather"] = WeatherSimulator.transition_weather(curr_weather, targ_weather, rate=0.08)
        
        # 3. Calculate Dynamic Visibility Range
        sim_state["visibility_m"] = VisibilityEngine.calculate_visibility(sim_state["weather"])
        sim_state["visibility_category"] = VisibilityEngine.get_visibility_category(sim_state["visibility_m"])
        
        # 4. Advance Road Degrade State (mud accumulation, cracks)
        RoadSimulator.update_road_conditions(sim_state["roads"], sim_state["weather"], dt)
        
        # Calculate dynamic road health and friction recommended speeds
        road_status_dict = {}
        for road in sim_state["roads"]:
            status_data = RoadHealth.calculate_road_status(
                base_quality=0.85 if "Loop" in road["name"] else 0.90, # mock base quality
                potholes=road["potholes"],
                water_accumulation=road["water_accumulation"],
                slope_deg=road["slope_deg"]
            )
            road["surface_quality"] = status_data["surface_quality"]
            road["risk_score"] = status_data["risk_score"]
            road["recommended_speed"] = status_data["recommended_speed"]
            road["status"] = status_data["status"]
            
            # Map road ID to road status for vehicles to read quickly
            road_status_dict[road["id"]] = road
            
        # 5. Process Active Road Laser Scanning UI animation
        scan = sim_state.get("active_road_scan")
        if scan and not scan["complete"]:
            scan["scan_progress"] += 15.0 * (dt / 0.5)
            if scan["scan_progress"] >= 100.0:
                scan["scan_progress"] = 100.0
                scan["complete"] = True
                # Scan identifies and reduces road hazard risk (clears visual markers)
                scanned_road = next((r for r in sim_state["roads"] if r["id"] == scan["road_id"]), None)
                if scanned_road:
                    scanned_road["potholes"] = max(0, scanned_road["potholes"] - 2)
                    scanned_road["water_accumulation"] = max(0.0, scanned_road["water_accumulation"] - 0.2)
        elif scan and scan["complete"]:
            # Leave visible for 3 seconds then clear
            scan["scan_progress"] += 5.0
            if scan["scan_progress"] >= 130.0:
                sim_state["active_road_scan"] = None
                
        # 6. Update Worker Positions
        for worker in sim_state["workers"]:
            WorkerSimulator.update_worker_position(worker, dt)
            
        # 7. Pre-compute Worker relative distances for Collision warning
        nearest_worker_per_veh = {}
        for v in sim_state["vehicles"]:
            nearest_w = {"distance_m": 999.0, "ttc_sec": 999.0, "worker_id": None}
            for w in sim_state["workers"]:
                w_ttc_info = CollisionEngine.calculate_worker_ttc(v, w)
                if w_ttc_info["distance_m"] < nearest_w["distance_m"]:
                    nearest_w["distance_m"] = w_ttc_info["distance_m"]
                    nearest_w["ttc_sec"] = w_ttc_info["ttc_sec"]
                    nearest_w["worker_id"] = w["id"]
            nearest_worker_per_veh[v["id"]] = nearest_w

        # --- REVIEW-2: AUTOMATIC MONSOON FLOODING TRIGGER ---
        rain = sim_state["weather"].get("rain", 0.0)
        h07_road = next((r for r in sim_state["roads"] if r["id"] == "H-07"), None)
        if rain > 85.0 and h07_road and h07_road.get("water_accumulation", 0.0) > 0.85:
            if not h07_road.get("is_blocked"):
                h07_road["is_restricted"] = True
                h07_road["is_blocked"] = True
                h07_road["status"] = "DANGEROUS"
                
                timestamp = time.strftime("%H:%M:%S")
                new_inc = {
                    "id": f"INC-AUTO-FL-{int(time.time())}",
                    "type": "Flooding",
                    "location": "Haul Road H-07",
                    "roadId": "H-07",
                    "severity": "CRITICAL",
                    "timestamp": timestamp,
                    "status": "ACTIVE",
                    "affectedVehicles": [],
                    "alternativeRoute": None
                }
                sim_state["incidents"].append(new_inc)
                sim_state["timeline"].append({"time": timestamp, "message": "CRITICAL: Monsoon causes severe flooding on H-07."})
                sim_state["timeline"].append({"time": timestamp, "message": "Road H-07 marked BLOCKED."})
                sim_state["timeline"].append({"time": timestamp, "message": "Fleet-wide safety alert issued."})
                
                active_veh_count = len(sim_state["vehicles"])
                sim_state["fleet_notifications"]["sent"] = active_veh_count
                sim_state["fleet_notifications"]["delivered"] = active_veh_count
                sim_state["fleet_notifications"]["acknowledged"] = max(0, active_veh_count - 1)
                sim_state["fleet_notifications"]["pending"] = 1 if active_veh_count > 0 else 0
                
                for vehicle in sim_state["vehicles"]:
                    route = vehicle.get("route", [])
                    route_idx = vehicle.get("route_index", 0)
                    affected = False
                    for i in range(route_idx, len(route) - 1):
                        if (route[i] == "N_BENCH2_SE" and route[i+1] == "N_BENCH1_E") or \
                           (route[i] == "N_BENCH1_E" and route[i+1] == "N_BENCH2_SE"):
                            affected = True
                            break
                    if affected:
                        new_inc["affectedVehicles"].append(vehicle["id"])
                        start_search = route[route_idx + 1] if (route_idx + 1 < len(route)) else vehicle["current_node"]
                        alt_path, cost = RouteEngine.calculate_safest_route(
                            start_node=start_search,
                            target_node=vehicle["target_node"],
                            nodes=sim_state["nodes"],
                            roads=sim_state["roads"],
                            workers=sim_state["workers"]
                        )
                        if alt_path:
                            vehicle["route"] = route[:route_idx+1] + alt_path[1:]
                            vehicle["alertStatus"] = "REROUTING"
                            new_inc["alternativeRoute"] = " → ".join(alt_path)
                            sim_state["timeline"].append({
                                "time": timestamp,
                                "message": f"Vehicle {vehicle['id']} rerouting dynamically around H-07."
                            })
                        else:
                            vehicle["recommended_speed_kmh"] = 0.0
                            vehicle["alertStatus"] = "STOPPED_NO_ROUTE"
                            sim_state["timeline"].append({
                                "time": timestamp,
                                "message": f"CRITICAL: No safe alternative route for {vehicle['id']}. Stop ordered."
                            })
                sim_state["fleet_notifications"]["acknowledged"] = active_veh_count
                sim_state["fleet_notifications"]["pending"] = 0

        # --- REVIEW-2: V2V PAIRWISE DISTANCE & BEARING ---
        for v in sim_state["vehicles"]:
            v["nearby_vehicles"] = []
            
        for i in range(len(sim_state["vehicles"])):
            for j in range(i + 1, len(sim_state["vehicles"])):
                v1 = sim_state["vehicles"][i]
                v2 = sim_state["vehicles"][j]
                
                dx = v2["position"]["x"] - v1["position"]["x"]
                dy = v2["position"]["y"] - v1["position"]["y"]
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist <= 500.0:
                    dir_1_to_2 = get_relative_direction(v1.get("heading", 0.0), dx, dy)
                    dir_2_to_1 = get_relative_direction(v2.get("heading", 0.0), -dx, -dy)
                    
                    v1["nearby_vehicles"].append({
                        "id": v2["id"],
                        "type": v2["type"],
                        "distance": round(dist, 1),
                        "direction": dir_1_to_2,
                        "priority": v2.get("priority", "NORMAL")
                    })
                    v2["nearby_vehicles"].append({
                        "id": v1["id"],
                        "type": v1["type"],
                        "distance": round(dist, 1),
                        "direction": dir_2_to_1,
                        "priority": v1.get("priority", "NORMAL")
                    })

        # --- REVIEW-2: EMERGENCY ROW PRIORITY CALCULATOR ---
        emergency_speed_limits = {}
        for vehicle in sim_state["vehicles"]:
            if vehicle.get("priority") == "EMERGENCY":
                for other in sim_state["vehicles"]:
                    if other["id"] != vehicle["id"] and other.get("priority") != "EMERGENCY":
                        dx = other["position"]["x"] - vehicle["position"]["x"]
                        dy = other["position"]["y"] - vehicle["position"]["y"]
                        dist = math.sqrt(dx*dx + dy*dy)
                        if dist < 200.0:
                            overlap = False
                            em_route = vehicle.get("route", [])
                            em_idx = vehicle.get("route_index", 0)
                            other_route = other.get("route", [])
                            other_idx = other.get("route_index", 0)
                            
                            em_upcoming = em_route[em_idx:em_idx+4]
                            other_upcoming = other_route[other_idx:other_idx+4]
                            
                            shared_nodes = set(em_upcoming).intersection(set(other_upcoming))
                            if shared_nodes or other["current_road"] == vehicle["current_road"]:
                                overlap = True
                                
                            if overlap:
                                if dist < 80.0:
                                    emergency_speed_limits[other["id"]] = 0.0
                                else:
                                    emergency_speed_limits[other["id"]] = min(emergency_speed_limits.get(other["id"], 999.0), 10.0)

        # 8. Sensor Simulation & Fusion Logic
        for vehicle in sim_state["vehicles"]:
            v_id = vehicle["id"]
            
            # Simulate sensor target lists for RGB, Thermal, Radar
            rgb_dets, therm_dets, rad_dets = SensorSimulator.generate_sensor_detections(
                vehicle=vehicle,
                other_vehicles=sim_state["vehicles"],
                workers=sim_state["workers"],
                weather_state=sim_state["weather"],
                visibility_m=sim_state["visibility_m"]
            )
            
            # Save raw lists in digital twin cache for rendering in Sensor Lab
            vehicle["raw_detections"] = {
                "rgb": rgb_dets,
                "thermal": therm_dets,
                "radar": rad_dets
            }
            
            # Execute Fusion
            fused_objs, overall_conf, sensor_confs = SensorFusion.fuse_sensors(
                rgb_detections=rgb_dets,
                thermal_detections=therm_dets,
                radar_detections=rad_dets,
                weather_state=sim_state["weather"],
                hardware_healths=vehicle["sensor_health"]
            )
            
            vehicle["fused_objects"] = fused_objs
            vehicle["perception_confidence"] = overall_conf
            vehicle["sensor_confidence"] = sensor_confs
            
            # 9. Compute Adaptive Speed recommendations based on multi-hazard constraints
            curr_road = road_status_dict.get(vehicle["current_road"], {"recommended_speed": 40.0})
            safe_speed = curr_road["recommended_speed"]
            
            # Apply weather visibility ceilings
            vis = sim_state["visibility_m"]
            if vis <= 5.0:
                safe_speed = min(safe_speed, 12.0)
            elif vis <= 15.0:
                safe_speed = min(safe_speed, 20.0)
            elif vis <= 30.0:
                safe_speed = min(safe_speed, 30.0)
                
            # Apply worker proximity speed ceiling
            v_nearest_w = nearest_worker_per_veh[v_id]
            if v_nearest_w["distance_m"] <= 25.0:
                safe_speed = min(safe_speed, 10.0)
            elif v_nearest_w["distance_m"] <= 45.0:
                safe_speed = min(safe_speed, 20.0)
                
            # Apply self-aware hardware degradation speed ceiling
            if overall_conf < 0.40:
                safe_speed = min(safe_speed, 15.0)
            if overall_conf < 0.15: # Total sensor failure
                safe_speed = 0.0 # Force Controlled Stop!
                
            # Apply Emergency Right-of-Way speed limits
            if v_id in emergency_speed_limits:
                safe_speed = min(safe_speed, emergency_speed_limits[v_id])
                
            # Apply Blockage Approach speed limits
            dist_to_block, blocked_road = get_distance_to_blockage(vehicle, sim_state["roads"], sim_state["nodes"])
            if blocked_road:
                if dist_to_block < 90.0:
                    safe_speed = 0.0
                    vehicle["alertStatus"] = "STOPPED_NEAR_BLOCKAGE"
                elif dist_to_block < 700.0:
                    safe_speed = min(safe_speed, 15.0)
                    
            vehicle["recommended_speed_kmh"] = round(safe_speed, 1)
            
            # Move vehicle
            VehicleSimulator.update_vehicle_position(vehicle, sim_state["nodes"], sim_state["roads"], dt)
            
        # 10. Vehicle-to-Vehicle Collision Tracking
        sim_state["active_conflicts"] = []
        for i in range(len(sim_state["vehicles"])):
            for j in range(i + 1, len(sim_state["vehicles"])):
                v1 = sim_state["vehicles"][i]
                v2 = sim_state["vehicles"][j]
                
                # Check spatial distance (mock limits)
                ttc_data = CollisionEngine.calculate_ttc_and_risk(v1, v2)
                
                # If TTC is threatening, save active conflict
                if ttc_data["ttc_sec"] <= 18.0:
                    sim_state["active_conflicts"].append({
                        "v1": v1["id"],
                        "v2": v2["id"],
                        "distance": ttc_data["distance_m"],
                        "closing_speed": ttc_data["closing_speed_mps"],
                        "ttc": ttc_data["ttc_sec"],
                        "road_id": v1["current_road"] if v1["current_road"] == v2["current_road"] else "Intersection"
                    })
                    
        # 11. Run Combined Risk Evaluator & Safety States
        for vehicle in sim_state["vehicles"]:
            v_id = vehicle["id"]
            
            # Find conflict matching this vehicle with lowest TTC
            v_ttc_info = {"ttc_sec": 999.0, "distance_m": 999.0}
            for c in sim_state["active_conflicts"]:
                if c["v1"] == v_id or c["v2"] == v_id:
                    if c["ttc"] < v_ttc_info["ttc_sec"]:
                        v_ttc_info = {"ttc_sec": c["ttc"], "distance_m": c["distance"]}
                        
            curr_road = road_status_dict.get(vehicle["current_road"], {"risk_score": 0.0})
            
            risk_data = RiskEngine.calculate_vehicle_risk(
                ttc_info=v_ttc_info,
                nearest_worker_info=nearest_worker_per_veh[v_id],
                road_status=curr_road,
                visibility_m=sim_state["visibility_m"],
                perception_conf=vehicle["perception_confidence"]
            )
            
            vehicle["risk_score"] = risk_data["risk_score"]
            vehicle["safety_state"] = risk_data["safety_state"]
            
            # If safety state is CRITICAL or HIGH RISK, override speed recommendations to BRAKE!
            if vehicle["safety_state"] == "CRITICAL":
                vehicle["recommended_speed_kmh"] = 0.0 # Force brake immediately
            elif vehicle["safety_state"] == "HIGH RISK":
                vehicle["recommended_speed_kmh"] = min(vehicle["recommended_speed_kmh"], 10.0)
                
        # 12. Safe Routing Engine: Handle Alternate Path Calculation
        if sim_state.get("trigger_reroute_v3", False):
            # Recalculate route for V-03 using Dijkstra
            v3 = next((v for v in sim_state["vehicles"] if v["id"] == "V-03"), None)
            if v3:
                # Close H-07 in routing cost calculation
                # safepath returns: ["N_BENCH3_E", "N_BENCH3_W", "N_BENCH2_NW", "N_BENCH2_SE", "N_BENCH1_E", "N_PARKING"...]
                # Let's set H-07 as restricted or high risk, and call engine
                degraded_road = next((r for r in sim_state["roads"] if r["id"] == "H-07"), None)
                if degraded_road:
                    degraded_road["is_restricted"] = True # Set flag to block Dijkstra node
                    
                path, cost = RouteEngine.calculate_safest_route(
                    start_node=v3["current_node"],
                    target_node=v3["target_node"],
                    nodes=sim_state["nodes"],
                    roads=sim_state["roads"],
                    workers=sim_state["workers"]
                )
                
                # Restore flag
                if degraded_road:
                    degraded_road["is_restricted"] = False
                    
                if path:
                    v3["route"] = path
                    v3["route_index"] = 0
                    scenario_engine.log_messages.append(f"V-03 Rerouted safely via East Rim Bypass (H-13) due to high risk on H-07. Cost: {round(cost, 1)}")
                    
            sim_state["trigger_reroute_v3"] = False
            
        # 13. Generate Priority-Based Explainable Alerts
        sim_state["alerts"] = AlertEngine.generate_alerts(
            vehicles=sim_state["vehicles"],
            workers=sim_state["workers"],
            weather=sim_state["weather"],
            roads=sim_state["roads"],
            active_conflicts=sim_state["active_conflicts"]
        )
        
        # Inject timestamp
        for alert in sim_state["alerts"]:
            alert["timestamp"] = time.strftime("%H:%M:%S")
            
        # 14. Update Analytics metrics
        sim_state["simulation_time"] += dt
        
        # Log values every 4 ticks (2 seconds)
        if int(sim_state["simulation_time"] * 2) % 4 == 0:
            hist = sim_state["analytics_history"]
            hist["time"].append(round(sim_state["simulation_time"], 1))
            hist["visibility"].append(sim_state["visibility_m"])
            hist["alerts_count"].append(len(sim_state["alerts"]))
            
            # Avg speed of active fleet
            speeds = [v["speed_kmh"] for v in sim_state["vehicles"] if v["status"] == "ACTIVE"]
            avg_s = sum(speeds) / len(speeds) if speeds else 0.0
            hist["avg_speed"].append(round(avg_s, 1))
            
            # Risk counts
            r_dist = {"NORMAL": 0, "CAUTION": 0, "HIGH_RISK": 0, "CRITICAL": 0}
            for v in sim_state["vehicles"]:
                s = v["safety_state"]
                if s == "HIGH RISK":
                    r_dist["HIGH_RISK"] += 1
                else:
                    r_dist[s] += 1
            hist["risk_distribution"] = r_dist
            
            # Cap history array length to keep memory bounds (last 30 ticks)
            if len(hist["time"]) > 30:
                hist["time"].pop(0)
                hist["visibility"].pop(0)
                hist["alerts_count"].pop(0)
                hist["avg_speed"].pop(0)

def simulation_worker_loop():
    """Background thread runner which ticks the simulator physics."""
    while True:
        tick_simulation(0.5)
        time.sleep(0.5)

# Start background thread
thread = threading.Thread(target=simulation_worker_loop, daemon=True)
thread.start()

# --- WEB ENDPOINTS ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/state", methods=["GET"])
def get_state():
    """API endpoint returns unified simulation parameters."""
    with state_lock:
        state_copy = dict(sim_state)
        # Add scenario logs to return message package
        state_copy["scenario_logs"] = scenario_engine.log_messages
        state_copy["scenario_active"] = scenario_engine.scenario_active
        state_copy["active_scenario_id"] = scenario_engine.active_scenario_id
        state_copy["scenario_time"] = round(scenario_engine.elapsed_time, 1)
        
        # Calculate mock efficiency parameters for the dashboard
        # Fulfills Section 35 & 36
        fleet_efficiency = 92.0
        visibility = sim_state["visibility_m"]
        if visibility < 10.0:
            # Low visibility drops efficiency without mineguard
            fleet_efficiency = 78.0 # With mineguard (keeps vehicles moving safely instead of 0%)
        elif visibility < 30.0:
            fleet_efficiency = 84.0
            
        state_copy["fleet_metrics"] = {
            "efficiency": fleet_efficiency,
            "before_mineguard_efficiency": 0.0 if visibility < 10.0 else (45.0 if visibility < 30.0 else 92.0), # Without mineguard, fleet is stopped
            "haul_cycle_min": round(25.0 + (120.0 - visibility)*0.15, 1),
            "before_mineguard_haul_cycle": 999.0 if visibility < 10.0 else round(38.0 + (120.0 - visibility)*0.4, 1)
        }
        
        return jsonify(state_copy)

@app.route("/api/simulation/control", methods=["POST"])
def simulation_control():
    """Starts, pauses, resumes or resets the state matrix."""
    data = request.json
    action = data.get("action")
    
    with state_lock:
        if action == "start" or action == "resume":
            sim_state["simulation_running"] = True
        elif action == "pause":
            sim_state["simulation_running"] = False
        elif action == "reset":
            load_initial_data()
            sim_state["simulation_running"] = True
            
    return jsonify({"status": "success", "running": sim_state["simulation_running"]})

@app.route("/api/simulation/scenario", methods=["POST"])
def select_scenario():
    """Activates one of the 8 predefined timeline scripts."""
    data = request.json
    scen_id = int(data.get("scenario_id"))
    
    with state_lock:
        # Reset to base state first to clear previous runs
        load_initial_data()
        
        # Start selected scenario
        scenario_engine.start_scenario(scen_id)
        
        # Set scenario configurations based on ID
        if scen_id == 7:
            # Main Bailadila Extreme Monsoon Demo
            # Reset vehicles to default start points
            load_initial_data()
            scenario_engine.start_scenario(7)
            
    return jsonify({"status": "success", "active_scenario": scen_id})

@app.route("/api/simulation/weather", methods=["POST"])
def update_weather():
    """Processes manual slide parameters to target weather values."""
    data = request.json
    
    with state_lock:
        # Update target weather in simulator
        weather_engine.update_weather(
            rain=data.get("rain"),
            wind=data.get("wind"),
            fog=data.get("fog"),
            humidity=data.get("humidity"),
            dust=data.get("dust"),
            clouds=data.get("clouds")
        )
        sim_state["target_weather"] = weather_engine.get_state()
        
        # Stop scenario to allow manual overrides
        if scenario_engine.scenario_active and scenario_engine.active_scenario_id != 7:
            scenario_engine.stop_scenario()
            
    return jsonify({"status": "success", "target_weather": sim_state["target_weather"]})

@app.route("/api/simulation/sensor-fail", methods=["POST"])
def trigger_sensor_fail():
    """Simulates physical mud occlusion or electrical sensor failure on dumpers."""
    data = request.json
    v_id = data.get("vehicle_id")
    sensor = data.get("sensor") # rgb, thermal, radar
    failed = data.get("failed", True) # boolean
    
    with state_lock:
        vehicle = next((v for v in sim_state["vehicles"] if v["id"] == v_id), None)
        if vehicle:
            # Set health value (0.1 means failed/mud occluded, 1.0 means active)
            vehicle["sensor_health"][sensor] = 0.05 if failed else 1.0
            
    return jsonify({"status": "success"})

@app.route("/api/simulation/road-scan", methods=["POST"])
def trigger_road_scan():
    """Simulates active haul-road laser scanning sweeps."""
    data = request.json
    road_id = data.get("road_id")
    
    with state_lock:
        sim_state["active_road_scan"] = {
            "road_id": road_id,
            "scan_progress": 0.0,
            "complete": False
        }
        
    return jsonify({"status": "success"})

@app.route("/api/simulation/speed-override", methods=["POST"])
def trigger_speed_override():
    """Toggles vehicle speed override to simulate driver speed violations."""
    data = request.json
    v_id = data.get("vehicle_id")
    speed = float(data.get("speed"))
    
    with state_lock:
        vehicle = next((v for v in sim_state["vehicles"] if v["id"] == v_id), None)
        if vehicle:
            # Set direct speed override (driver ignore recommendation)
            # This causes recommendation speed discrepancies (speed violation!)
            vehicle["speed_kmh"] = speed
            # Break operator tracking match loop for 3 seconds
            vehicle["recommended_speed_kmh"] = max(5.0, vehicle["recommended_speed_kmh"] - 10)
            
    return jsonify({"status": "success"})

@app.route("/api/simulation/add-vehicle", methods=["POST"])
def add_vehicle():
    data = request.json
    veh_id = data.get("id")
    veh_type = data.get("type", "Dumper")
    name = data.get("name", veh_id)
    start_node = data.get("start_node")
    target_node = data.get("target_node")
    speed = float(data.get("speed", 30))
    priority = data.get("priority", "NORMAL")
    
    with state_lock:
        node = next((n for n in sim_state["nodes"] if n["id"] == start_node), None)
        if not node:
            return jsonify({"status": "error", "message": f"Starting node {start_node} not found."}), 400
            
        path, cost = RouteEngine.calculate_safest_route(
            start_node=start_node,
            target_node=target_node,
            nodes=sim_state["nodes"],
            roads=sim_state["roads"],
            workers=sim_state["workers"]
        )
        
        if not path:
            return jsonify({"status": "error", "message": f"No valid route found between {start_node} and {target_node}."}), 400
            
        curr_road = None
        for road in sim_state["roads"]:
            if (road["start_node"] == path[0] and road["end_node"] == path[1]) or \
               (road["start_node"] == path[1] and road["end_node"] == path[0]):
                curr_road = road["id"]
                break
                
        new_veh = {
            "id": veh_id,
            "name": name,
            "type": veh_type,
            "status": "ACTIVE",
            "current_node": start_node,
            "target_node": target_node,
            "speed_kmh": speed,
            "max_speed_kmh": 60.0 if veh_type in ["Ambulance", "Rescue Vehicle", "Service Vehicle"] else 50.0,
            "position": {"x": float(node["x"]), "y": float(node["y"])},
            "heading": 0.0,
            "current_road": curr_road,
            "sensor_status": {"rgb": "OK", "thermal": "OK", "radar": "OK"},
            "sensor_health": {"rgb": 1.0, "thermal": 1.0, "radar": 1.0},
            "sensor_confidence": {"rgb": 1.0, "thermal": 1.0, "radar": 1.0},
            "risk_score": 0.0,
            "safety_state": "NORMAL",
            "recommended_speed_kmh": speed,
            "route": path,
            "route_index": 0,
            "priority": priority,
            "communicationStatus": "ONLINE",
            "alertStatus": "NOMINAL",
            "nearby_vehicles": []
        }
        
        sim_state["vehicles"].append(new_veh)
        
        timestamp = time.strftime("%H:%M:%S")
        sim_state["timeline"].append({
            "time": timestamp,
            "message": f"Vehicle {veh_id} ({veh_type}) added at {start_node}. Destination: {target_node}."
        })
        
    return jsonify({"status": "success", "vehicle": new_veh})

@app.route("/api/simulation/report-incident", methods=["POST"])
def report_incident():
    data = request.json
    inc_type = data.get("type", "Rockfall")
    road_id = data.get("roadId")
    severity = data.get("severity", "CRITICAL")
    
    with state_lock:
        road = next((r for r in sim_state["roads"] if r["id"] == road_id), None)
        if not road:
            return jsonify({"status": "error", "message": f"Road {road_id} not found."}), 400
            
        road["is_restricted"] = True
        road["is_blocked"] = True
        road["status"] = "DANGEROUS"
        
        timestamp = time.strftime("%H:%M:%S")
        
        new_inc = {
            "id": f"INC-{int(time.time())}",
            "type": inc_type,
            "location": f"Haul Road {road_id}",
            "roadId": road_id,
            "severity": severity,
            "timestamp": timestamp,
            "status": "ACTIVE",
            "affectedVehicles": [],
            "alternativeRoute": None
        }
        
        sim_state["incidents"].append(new_inc)
        
        sim_state["timeline"].append({"time": timestamp, "message": f"Incident reported: {inc_type} on road {road_id}."})
        sim_state["timeline"].append({"time": timestamp, "message": f"Road {road_id} marked BLOCKED."})
        sim_state["timeline"].append({"time": timestamp, "message": "Fleet-wide safety alert issued."})
        
        active_veh_count = len(sim_state["vehicles"])
        sim_state["fleet_notifications"]["sent"] = active_veh_count
        sim_state["fleet_notifications"]["delivered"] = active_veh_count
        sim_state["fleet_notifications"]["acknowledged"] = max(0, active_veh_count - 1)
        sim_state["fleet_notifications"]["pending"] = 1 if active_veh_count > 0 else 0
        
        for vehicle in sim_state["vehicles"]:
            route = vehicle.get("route", [])
            route_idx = vehicle.get("route_index", 0)
            
            affected = False
            for i in range(route_idx, len(route) - 1):
                node_u = route[i]
                node_v = route[i+1]
                if (road["start_node"] == node_u and road["end_node"] == node_v) or \
                   (road["start_node"] == node_v and road["end_node"] == node_u):
                    affected = True
                    break
                    
            if affected:
                new_inc["affectedVehicles"].append(vehicle["id"])
                
                start_search = route[route_idx + 1] if (route_idx + 1 < len(route)) else vehicle["current_node"]
                alt_path, cost = RouteEngine.calculate_safest_route(
                    start_node=start_search,
                    target_node=vehicle["target_node"],
                    nodes=sim_state["nodes"],
                    roads=sim_state["roads"],
                    workers=sim_state["workers"]
                )
                
                if alt_path:
                    vehicle["route"] = route[:route_idx+1] + alt_path[1:]
                    vehicle["alertStatus"] = "REROUTING"
                    new_inc["alternativeRoute"] = " → ".join(alt_path)
                    sim_state["timeline"].append({
                        "time": timestamp,
                        "message": f"Vehicle {vehicle['id']} rerouting dynamically around blockage. Route: {' → '.join(alt_path)}"
                    })
                else:
                    vehicle["recommended_speed_kmh"] = 0.0
                    vehicle["alertStatus"] = "STOPPED_NO_ROUTE"
                    sim_state["timeline"].append({
                        "time": timestamp,
                        "message": f"CRITICAL: No safe alternative route for {vehicle['id']}. Stop ordered."
                    })
            else:
                sim_state["timeline"].append({
                    "time": timestamp,
                    "message": f"Vehicle {vehicle['id']} unaffected by blockage."
                })
                
        sim_state["fleet_notifications"]["acknowledged"] = active_veh_count
        sim_state["fleet_notifications"]["pending"] = 0
        
    return jsonify({"status": "success", "incident": new_inc})

@app.route("/api/simulation/connectivity", methods=["POST"])
def toggle_connectivity():
    data = request.json
    veh_id = data.get("vehicle_id")
    action = data.get("action")
    
    with state_lock:
        vehicle = next((v for v in sim_state["vehicles"] if v["id"] == veh_id), None)
        if vehicle:
            timestamp = time.strftime("%H:%M:%S")
            if action == "disconnect":
                vehicle["communicationStatus"] = "DEGRADED"
                sim_state["timeline"].append({
                    "time": timestamp,
                    "message": f"Warning: Vehicle {veh_id} communication DEGRADED. Control room tracking lost."
                })
            else:
                vehicle["communicationStatus"] = "ONLINE"
                sim_state["timeline"].append({
                    "time": timestamp,
                    "message": f"Connection restored for Vehicle {veh_id}. Syncing..."
                })
                
    return jsonify({"status": "success", "vehicle_id": veh_id, "communicationStatus": vehicle["communicationStatus"] if vehicle else "UNKNOWN"})

@app.route("/api/simulation/resolve-incident", methods=["POST"])
def resolve_incident():
    data = request.json or {}
    road_id = data.get("roadId")
    
    with state_lock:
        incident = next((inc for inc in sim_state["incidents"] if inc["roadId"] == road_id), None)
        if incident:
            sim_state["incidents"].remove(incident)
            
            # Unblock the road
            road = next((r for r in sim_state["roads"] if r["id"] == road_id), None)
            if road:
                road["is_blocked"] = False
                road["is_restricted"] = False
            
            timestamp = time.strftime("%H:%M:%S")
            sim_state["timeline"].append({
                "time": timestamp,
                "message": f"🚧 Incident on {road_id} resolved. Road segment reopened."
            })
            
            # Recalculate routes for all active vehicles to see if they can resume normal paths
            for vehicle in sim_state["vehicles"]:
                if vehicle["status"] == "ACTIVE":
                    route = vehicle.get("route", [])
                    route_idx = vehicle.get("route_index", 0)
                    curr_node = route[route_idx]
                    
                    alt_path, cost = RouteEngine.calculate_safest_route(
                        start_node=curr_node,
                        target_node=vehicle["target_node"],
                        nodes=sim_state["nodes"],
                        roads=sim_state["roads"],
                        workers=sim_state["workers"]
                    )
                    
                    if alt_path:
                        vehicle["route"] = route[:route_idx+1] + alt_path[1:]
                        vehicle["alertStatus"] = "NORMAL"
                        # Reset speed to max limit or default speed
                        vehicle["recommended_speed_kmh"] = vehicle.get("max_speed_limit", 35.0)
                        sim_state["timeline"].append({
                            "time": timestamp,
                            "message": f"Vehicle {vehicle['id']} recalculated route via reopened road {road_id}."
                        })
            
            return jsonify({"status": "success", "message": f"Incident on {road_id} resolved."})
        else:
            return jsonify({"status": "error", "message": f"No active incident found on road {road_id}."}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

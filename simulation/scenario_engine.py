class ScenarioEngine:
    def __init__(self):
        self.active_scenario_id = None
        self.elapsed_time = 0.0 # seconds
        self.scenario_active = False
        self.log_messages = []
        
    def start_scenario(self, scenario_id):
        self.active_scenario_id = int(scenario_id)
        self.elapsed_time = 0.0
        self.scenario_active = True
        self.log_messages = [f"Started Scenario {scenario_id}."]
        
    def stop_scenario(self):
        self.scenario_active = False
        
    def reset_scenario(self):
        self.active_scenario_id = None
        self.elapsed_time = 0.0
        self.scenario_active = False
        self.log_messages = []
        
    def step_scenario(self, state, dt=0.5):
        """
        Processes scenario events based on the elapsed simulation time.
        Injects modifications directly into the state (vehicles, workers, weather, roads).
        """
        if not self.scenario_active or self.active_scenario_id is None:
            return
            
        self.elapsed_time += dt
        
        # Load scenarios config (which app.py will read and pass, or we parse from state)
        scenarios_data = state.get("scenarios_config", [])
        active_config = next((s for s in scenarios_data if s["id"] == self.active_scenario_id), None)
        
        if not active_config:
            return
            
        steps = active_config.get("steps", [])
        
        for step in steps:
            t = step["time"]
            # Trigger event if current time is within this tick window
            if t <= self.elapsed_time < t + dt:
                action = step["action"]
                params = step.get("params", {})
                
                self.log_messages.append(f"[{int(self.elapsed_time)}s] Action: {action} with params {params}")
                
                if action == "set_weather":
                    # Update target weather in state
                    state["target_weather"] = params
                    
                elif action == "trigger_conflict":
                    # Force V-01 and V-02 onto the same road segment
                    v1_id = params["v1"]
                    v2_id = params["v2"]
                    road_id = params["road"]
                    
                    v1 = next((v for v in state["vehicles"] if v["id"] == v1_id), None)
                    v2 = next((v for v in state["vehicles"] if v["id"] == v2_id), None)
                    road = next((r for r in state["roads"] if r["id"] == road_id), None)
                    
                    if v1 and v2 and road:
                        # Place V-01 at the starting node of the road
                        # Place V-02 at the ending node of the road, and set their route index
                        v1["current_road"] = road_id
                        v2["current_road"] = road_id
                        
                        # Direct route collision
                        v1["current_node"] = road["start_node"]
                        v1["route"] = [road["start_node"], road["end_node"]]
                        v1["route_index"] = 0
                        # Calculate starting coordinates
                        ns = next((n for n in state["nodes"] if n["id"] == road["start_node"]), None)
                        if ns:
                            v1["position"]["x"] = ns["x"]
                            v1["position"]["y"] = ns["y"]
                            
                        v2["current_node"] = road["end_node"]
                        v2["route"] = [road["end_node"], road["start_node"]]
                        v2["route_index"] = 0
                        ne = next((n for n in state["nodes"] if n["id"] == road["end_node"]), None)
                        if ne:
                            v2["position"]["x"] = ne["x"]
                            v2["position"]["y"] = ne["y"]
                            
                        # Increase speeds to show collision warning
                        v1["speed_kmh"] = 42.0
                        v2["speed_kmh"] = 36.0
                        
                elif action == "move_worker":
                    # Move worker W-04 directly into a vehicle's path
                    worker_id = params["worker_id"]
                    x, y = params["x"], params["y"]
                    
                    worker = next((w for w in state["workers"] if w["id"] == worker_id), None)
                    if worker:
                        worker["position"]["x"] = x
                        worker["position"]["y"] = y
                        worker["status"] = "STATIONARY" # Keep them there for the warning
                        
                elif action == "degrade_road":
                    road_id = params["road_id"]
                    potholes = params["potholes"]
                    water = params["water"]
                    
                    road = next((r for r in state["roads"] if r["id"] == road_id), None)
                    if road:
                        road["potholes"] = potholes
                        road["water_accumulation"] = water
                        
                elif action == "road_scan":
                    # Triggers the road scanner visual on the frontend
                    state["active_road_scan"] = {
                        "road_id": params["road_id"],
                        "scan_progress": 0.0,
                        "complete": False
                    }
                    
                elif action == "fail_sensor":
                    v_id = params["vehicle_id"]
                    sensor = params["sensor"]
                    health = params["health"]
                    
                    v = next((v for v in state["vehicles"] if v["id"] == v_id), None)
                    if v:
                        v["sensor_health"][sensor] = health
                        
                elif action == "reroute_vehicle":
                    v_id = params["vehicle_id"]
                    v = next((v for v in state["vehicles"] if v["id"] == v_id), None)
                    if v:
                        # Reroute V-03 around the blocked N_BENCH2_SE (H-07)
                        # Normally N_BENCH3_E -> N_BENCH3_W -> N_BENCH2_NW -> N_BENCH2_SE -> N_BENCH1_E...
                        # But since H-07 is degraded, routing engine calculates bypass:
                        # H-07 is restricted or too high cost. Safest route uses bypass.
                        # Force route recalculate on the next tick
                        state["trigger_reroute_v3"] = True
                        
                elif action == "complete":
                    self.scenario_active = False
                    self.log_messages.append(f"Scenario {self.active_scenario_id} completed successfully.")

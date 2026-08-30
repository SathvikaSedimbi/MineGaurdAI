import math

class CollisionEngine:
    @staticmethod
    def calculate_ttc_and_risk(v1_state, v2_state, road_link=None):
        """
        Calculates the Time-To-Collision (TTC) and relative closing speed between two vehicles.
        Supports both vector mathematics and road segment projection.
        """
        x1, y1 = v1_state["position"]["x"], v1_state["position"]["y"]
        x2, y2 = v2_state["position"]["x"], v2_state["position"]["y"]
        
        # Distance (mock scale: 1 pixel = 1 meter)
        dx = x2 - x1
        dy = y2 - y1
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Convert speeds to m/s
        s1 = v1_state["speed_kmh"] / 3.6
        s2 = v2_state["speed_kmh"] / 3.6
        
        # If they are on the same road segment
        same_road = (v1_state.get("current_road") == v2_state.get("current_road") and 
                     v1_state.get("current_road") is not None)
        
        # Calculate headings in radians
        h1 = math.radians(v1_state.get("heading", 0))
        h2 = math.radians(v2_state.get("heading", 0))
        
        # Velocity vectors
        vx1, vy1 = s1 * math.cos(h1), s1 * math.sin(h1)
        vx2, vy2 = s2 * math.cos(h2), s2 * math.sin(h2)
        
        # Relative velocity vector (v1 relative to v2)
        dvx = vx1 - vx2
        dvy = vy1 - vy2
        
        # Closing speed: dot product of relative velocity and unit position vector
        # Positive values mean vehicles are closing in on each other.
        if distance > 0:
            ux = dx / distance
            uy = dy / distance
            # Projection of relative velocity vector onto the line of sight
            closing_speed = -(dvx * ux + dvy * uy) 
        else:
            closing_speed = 0.0
            
        # In a mine road, if they are on the same road and moving toward each other, 
        # let's override with road-segment logic which is much safer for curves.
        if same_road:
            # Check if they are moving towards each other based on their routes
            v1_route = v1_state.get("route", [])
            v2_route = v2_state.get("route", [])
            v1_idx = v1_state.get("route_index", 0)
            v2_idx = v2_state.get("route_index", 0)
            
            if (v1_idx + 1 < len(v1_route)) and (v2_idx + 1 < len(v2_route)):
                v1_next = v1_route[v1_idx + 1]
                v2_next = v2_route[v2_idx + 1]
                v1_curr = v1_route[v1_idx]
                v2_curr = v2_route[v2_idx]
                
                # If opposite directions on same link
                if v1_next == v2_curr and v2_next == v1_curr:
                    closing_speed = s1 + s2
                    
        # Calculate TTC
        if closing_speed > 0.1:
            ttc = distance / closing_speed
        else:
            ttc = 999.0 # Safe / No collision path
            
        return {
            "distance_m": round(distance, 1),
            "closing_speed_mps": round(closing_speed, 2),
            "ttc_sec": round(ttc, 2) if ttc < 100 else 999.0
        }

    @staticmethod
    def calculate_worker_ttc(vehicle_state, worker_state):
        """
        Calculates distance and collision vector between a heavy vehicle and a worker.
        """
        xv, yv = vehicle_state["position"]["x"], vehicle_state["position"]["y"]
        xw, yw = worker_state["position"]["x"], worker_state["position"]["y"]
        
        dx = xw - xv
        dy = yw - yv
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Vehicle speed in m/s
        sv = vehicle_state["speed_kmh"] / 3.6
        hv = math.radians(vehicle_state.get("heading", 0))
        
        vx, vy = sv * math.cos(hv), sv * math.sin(hv)
        
        # If moving towards the worker, project speed onto separation vector
        if distance > 0:
            ux = dx / distance
            uy = dy / distance
            closing_speed = vx * ux + vy * uy
        else:
            closing_speed = 0.0
            
        if closing_speed > 0.1:
            ttc = distance / closing_speed
        else:
            ttc = 999.0
            
        return {
            "distance_m": round(distance, 1),
            "closing_speed_mps": round(closing_speed, 2),
            "ttc_sec": round(ttc, 2) if ttc < 100 else 999.0
        }

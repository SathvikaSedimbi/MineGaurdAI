import math

class VehicleSimulator:
    @staticmethod
    def update_vehicle_position(vehicle, nodes, roads, dt=0.5):
        """
        Advances a single vehicle along its route. Reversing the path upon arrival
        at the destination to simulate continuous mine cycle haul operations.
        """
        route = vehicle.get("route", [])
        route_idx = vehicle.get("route_index", 0)
        
        if not route or len(route) < 2:
            return
            
        # Current node and next node
        curr_node_id = route[route_idx]
        
        # If vehicle reached final node, reverse its cycle
        if route_idx >= len(route) - 1:
            # Reverse route
            vehicle["route"] = list(reversed(route))
            vehicle["route_index"] = 0
            vehicle["current_node"] = vehicle["route"][0]
            vehicle["target_node"] = vehicle["route"][-1]
            route_idx = 0
            curr_node_id = vehicle["route"][0]
            
        next_node_id = vehicle["route"][route_idx + 1]
        
        # Get nodes data
        node_a = next((n for n in nodes if n["id"] == curr_node_id), None)
        node_b = next((n for n in nodes if n["id"] == next_node_id), None)
        
        if not node_a or not node_b:
            return
            
        # Find which road connects these nodes to update current_road attribute
        connected_road = None
        for road in roads:
            if (road["start_node"] == curr_node_id and road["end_node"] == next_node_id) or \
               (road["start_node"] == next_node_id and road["end_node"] == curr_node_id):
                connected_road = road["id"]
                break
        if connected_road:
            vehicle["current_road"] = connected_road
            
        # Vector from Node A to Node B
        x_a, y_a = node_a["x"], node_a["y"]
        x_b, y_b = node_b["x"], node_b["y"]
        
        dx = x_b - x_a
        dy = y_b - y_a
        segment_len = math.sqrt(dx*dx + dy*dy)
        
        # Calculate heading
        angle_rad = math.atan2(dy, dx)
        vehicle["heading"] = round(math.degrees(angle_rad), 1)
        
        # Current position
        pos_x = vehicle["position"]["x"]
        pos_y = vehicle["position"]["y"]
        
        # Distance to next node
        rem_dx = x_b - pos_x
        rem_dy = y_b - pos_y
        rem_dist = math.sqrt(rem_dx*rem_dx + rem_dy*rem_dy)
        
        # Target Speed Control: Adjust current speed towards recommended speed
        rec_speed = vehicle.get("recommended_speed_kmh", 30.0)
        curr_speed = vehicle.get("speed_kmh", 0.0)
        
        # Simulate operator response: braking is fast, acceleration is slow
        if curr_speed > rec_speed:
            curr_speed = max(rec_speed, curr_speed - 6.0 * dt) # Decelerate
        elif curr_speed < rec_speed:
            # Cap at max vehicle speed capability
            max_speed = vehicle.get("max_speed_kmh", 50.0)
            curr_speed = min(min(rec_speed, max_speed), curr_speed + 2.0 * dt) # Accelerate
            
        vehicle["speed_kmh"] = round(curr_speed, 1)
        
        # Distance to travel in meters (speed converted to m/s * dt)
        speed_mps = curr_speed / 3.6
        travel_dist = speed_mps * dt
        
        # Move vehicle position
        if travel_dist >= rem_dist:
            # We reach the node in this tick
            vehicle["position"]["x"] = x_b
            vehicle["position"]["y"] = y_b
            vehicle["route_index"] += 1
            vehicle["current_node"] = next_node_id
        else:
            # Move along the vector
            ux = dx / segment_len
            uy = dy / segment_len
            vehicle["position"]["x"] = round(pos_x + ux * travel_dist, 2)
            vehicle["position"]["y"] = round(pos_y + uy * travel_dist, 2)

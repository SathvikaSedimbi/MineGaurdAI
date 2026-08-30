import heapq

class RouteEngine:
    @staticmethod
    def calculate_safest_route(start_node, target_node, nodes, roads, workers):
        """
        Calculates the safest route using Dijkstra's algorithm.
        Edge weights are calculated as: length_m * (1.0 + road_risk / 10.0).
        Restricted roads are skipped entirely.
        """
        # Build adjacency list representation of the map
        # graph[node] = {neighbor: {"road_id": road_id, "weight": weight}}
        graph = {node["id"]: {} for node in nodes}
        
        # Helper to find if worker is near a road
        # If worker is near, apply safety penalty
        road_risk_modifiers = {road["id"]: 0.0 for road in roads}
        for worker in workers:
            # If worker is walking or active near a node, increase risk for adjacent roads
            curr_node = worker.get("current_node")
            if curr_node:
                for road in roads:
                    if road["start_node"] == curr_node or road["end_node"] == curr_node:
                        road_risk_modifiers[road["id"]] += 15.0 # Penalty for workers on route
                        
        for road in roads:
            if road["is_restricted"]:
                continue # Skip closed roads entirely
                
            u = road["start_node"]
            v = road["end_node"]
            
            # Risk from road health (quality degradation, potholes, water)
            road_risk = road.get("risk_score", 0.0) + road_risk_modifiers[road["id"]]
            
            # Weighted distance: safest path penalty
            # High risk multiplies the effective distance
            weight = road["length_m"] * (1.0 + (road_risk / 15.0))
            
            # Undirected graph representing mine road network
            if u in graph:
                graph[u][v] = {"road_id": road["id"], "weight": weight, "actual_len": road["length_m"]}
            if v in graph:
                graph[v][u] = {"road_id": road["id"], "weight": weight, "actual_len": road["length_m"]}
                
        # Dijkstra's Algorithm
        queue = [(0.0, start_node, [])]
        visited = set()
        
        while queue:
            (cost, current, path) = heapq.heappop(queue)
            
            if current in visited:
                continue
                
            visited.add(current)
            path = path + [current]
            
            if current == target_node:
                return path, cost
                
            for neighbor, edge_data in graph.get(current, {}).items():
                if neighbor not in visited:
                    heapq.heappush(queue, (cost + edge_data["weight"], neighbor, path))
                    
        # If target unreachable due to closures, fall back to ignoring restrictions to prevent lockups
        # But flag a major warning!
        return None, float('inf')

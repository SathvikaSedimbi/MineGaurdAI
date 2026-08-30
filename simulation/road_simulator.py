import random

class RoadSimulator:
    @staticmethod
    def update_road_conditions(roads, weather_state, dt=0.5):
        """
        Simulates road degradation dynamically based on weather conditions.
        Rain increases water levels and generates potholes on dirt ramp links.
        """
        rain = weather_state.get("rain", 0.0)
        
        for road in roads:
            # Water accumulation rate depends on slope (steeper roads drain faster, low areas accumulate)
            slope = road.get("slope_deg", 0.0)
            drainage_factor = 1.0 + (slope / 10.0)
            
            curr_water = road.get("water_accumulation", 0.0)
            
            if rain > 15.0:
                # Accumulate water
                acc_rate = 0.005 * (rain / 100.0) * (dt / 0.5)
                # Pit bottom (H-01) accumulates the most water due to gravity drainage
                if road["start_node"] == "N_PIT_LOAD" or road["end_node"] == "N_PIT_LOAD":
                    acc_rate *= 1.8
                new_water = curr_water + (acc_rate / drainage_factor)
                road["water_accumulation"] = round(min(1.0, new_water), 3)
            else:
                # Dry up / Drain
                evap_rate = 0.01 * (dt / 0.5) * drainage_factor
                new_water = curr_water - evap_rate
                road["water_accumulation"] = round(max(0.0, new_water), 3)
                
            # Dynamic pothole formation: wet soil under heavy dumper traffic forms potholes
            # If road water accumulation > 30%, increase chance of pothole creation
            if road["water_accumulation"] > 0.30 and rain > 50.0:
                # 0.5% chance per second of a pothole appearing during heavy rain
                chance = 0.005 * (dt / 0.5)
                if random.random() < chance:
                    road["potholes"] = min(15, road.get("potholes", 0) + 1)
                    
            # If weather is clear and dry, maintenance crews slowly fix potholes
            if rain == 0.0 and road["water_accumulation"] == 0.0:
                chance = 0.001 * (dt / 0.5) # slow repair
                if random.random() < chance:
                    road["potholes"] = max(0, road.get("potholes", 0) - 1)

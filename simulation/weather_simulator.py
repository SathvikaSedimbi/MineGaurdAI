class WeatherSimulator:
    @staticmethod
    def transition_weather(current_weather, target_weather, rate=0.08):
        """
        Smoothly interpolates weather parameters from current state to target state
        to simulate realistic environmental transitions.
        """
        updated = {}
        for key in ["rain", "wind", "fog", "humidity", "dust", "clouds"]:
            curr_val = current_weather.get(key, 0.0)
            targ_val = target_weather.get(key, curr_val)
            
            # Interpolation step
            diff = targ_val - curr_val
            if abs(diff) < 0.2:
                updated[key] = targ_val
            else:
                updated[key] = round(curr_val + diff * rate, 2)
                
        return updated

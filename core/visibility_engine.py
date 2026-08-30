import math

class VisibilityEngine:
    @staticmethod
    def calculate_visibility(weather_state):
        """
        Calculates visibility in meters based on rain, wind, fog, and dust.
        In severe conditions, visibility drops to 3-5 meters.
        """
        rain = weather_state.get("rain", 0.0)
        fog = weather_state.get("fog", 0.0)
        dust = weather_state.get("dust", 0.0)
        
        # Max baseline visibility is 150 meters in open cast mine
        base_visibility = 150.0
        
        # Fog exponential decay: at 100% fog, visibility drops to ~2.7m
        # V_fog = base * e^(-0.04 * fog)
        v_fog = base_visibility * math.exp(-0.04 * fog)
        
        # Rain linear/quadratic decay: at 100% rain, visibility drops to 15% of base
        v_rain = base_visibility * (1.0 - 0.85 * (rain / 100.0))
        
        # Dust decay: wind-driven dust obscures vision, at 100% dust visibility drops to ~10m
        v_dust = base_visibility * math.exp(-0.027 * dust)
        
        # Fused visibility is the minimum of the three factors (most restrictive dominates)
        visibility = min(v_fog, v_rain, v_dust)
        
        # Clip to ensure physical limits in extreme conditions (3m to 150m)
        visibility = max(3.0, min(150.0, visibility))
        return round(visibility, 1)

    @staticmethod
    def get_visibility_category(visibility_m):
        if visibility_m >= 100.0:
            return "CLEAR"
        elif visibility_m >= 30.0:
            return "LIGHT FOG"
        elif visibility_m >= 15.0:
            return "MODERATE FOG"
        elif visibility_m >= 8.0:
            return "DENSE FOG"
        else:
            return "EXTREME LOW VISIBILITY"

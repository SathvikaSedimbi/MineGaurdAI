class RoadHealth:
    @staticmethod
    def calculate_road_status(base_quality, potholes, water_accumulation, slope_deg):
        """
        Determines the dynamic road status, recommended speed, and safety level
        based on physical road properties and weather deterioration.
        """
        # Calculate dynamic surface quality (water reduces surface quality)
        surface_quality = max(0.10, base_quality - 0.45 * water_accumulation)
        
        # Determine risk score based on slope, potholes, and water
        # Higher slope and water increase traction slip risk
        slope_factor = slope_deg / 15.0 # Max typical bench incline is 15 deg
        risk_score = (potholes * 8.0) + (water_accumulation * 50.0) + (slope_factor * 20.0)
        risk_score = min(100.0, risk_score)
        
        # Calculate recommended speed (km/h)
        # Base speed on haul road is typically 40 km/h
        recommended_speed = 40.0
        
        # Apply reductions
        recommended_speed -= (potholes * 2.0)
        recommended_speed -= (water_accumulation * 25.0)
        if slope_deg > 6:
            recommended_speed -= (slope_deg - 6) * 1.5
            
        # Ensure recommended speed stays in bounds (10 km/h to 45 km/h)
        recommended_speed = max(10.0, min(45.0, recommended_speed))
        
        # Status labels
        if risk_score >= 70.0:
            status = "DANGEROUS"
        elif risk_score >= 40.0:
            status = "CAUTION"
        else:
            status = "SAFE"
            
        return {
            "surface_quality": round(surface_quality, 2),
            "risk_score": round(risk_score, 1),
            "recommended_speed": round(recommended_speed, 1),
            "status": status
        }

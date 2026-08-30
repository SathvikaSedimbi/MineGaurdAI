class RiskEngine:
    @staticmethod
    def calculate_vehicle_risk(ttc_info, nearest_worker_info, road_status, visibility_m, perception_conf):
        """
        Integrates multiple risk vectors to compute a unified risk score (0-100)
        and outputs the adaptive safety state: NORMAL, CAUTION, HIGH RISK, or CRITICAL.
        """
        # 1. Base Risk from Time-To-Collision (TTC)
        ttc = ttc_info.get("ttc_sec", 999.0)
        dist = ttc_info.get("distance_m", 999.0)
        
        ttc_risk = 0.0
        if ttc <= 4.0:
            ttc_risk = 95.0
        elif ttc <= 8.0:
            ttc_risk = 80.0
        elif ttc <= 12.0:
            ttc_risk = 60.0
        elif ttc <= 20.0:
            ttc_risk = 35.0
        elif dist < 30.0: # Even if closing speed is slow, proximity holds base risk
            ttc_risk = 40.0
            
        # 2. Risk from Worker Proximity
        w_dist = nearest_worker_info.get("distance_m", 999.0)
        w_ttc = nearest_worker_info.get("ttc_sec", 999.0)
        
        worker_risk = 0.0
        if w_dist <= 15.0 or w_ttc <= 5.0:
            worker_risk = 95.0
        elif w_dist <= 30.0 or w_ttc <= 10.0:
            worker_risk = 75.0
        elif w_dist <= 50.0:
            worker_risk = 40.0
            
        # 3. Risk from Environment (Visibility and Road degradation)
        road_risk = road_status.get("risk_score", 0.0)
        
        vis_risk = 0.0
        if visibility_m <= 5.0:
            vis_risk = 40.0
        elif visibility_m <= 15.0:
            vis_risk = 25.0
        elif visibility_m <= 30.0:
            vis_risk = 15.0
            
        # Combine hazards: we take the maximum threat as dominant, and layer environmental factors
        base_hazard_risk = max(ttc_risk, worker_risk)
        
        # Add a fraction of environmental and road risk to build overall score
        combined_risk = base_hazard_risk + (road_risk * 0.15) + (vis_risk * 0.25)
        
        # Self-awareness correction: If perception is severely degraded, increase danger representation
        if perception_conf <= 0.20:
            combined_risk = max(combined_risk, 85.0) # Force warning state
        elif perception_conf <= 0.50:
            combined_risk = max(combined_risk, 50.0)
            
        # Cap combined risk at 100
        combined_risk = round(min(100.0, combined_risk), 1)
        
        # 4. Map Risk score to Safety State
        if combined_risk >= 85.0 or ttc <= 5.0 or w_dist <= 15.0:
            state = "CRITICAL"
        elif combined_risk >= 60.0 or ttc <= 10.0 or w_dist <= 30.0:
            state = "HIGH RISK"
        elif combined_risk >= 30.0 or visibility_m <= 15.0 or road_risk >= 50.0 or perception_conf <= 0.50:
            state = "CAUTION"
        else:
            state = "NORMAL"
            
        return {
            "risk_score": combined_risk,
            "safety_state": state
        }

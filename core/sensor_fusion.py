class SensorFusion:
    @staticmethod
    def calculate_sensor_confidences(weather_state, hardware_healths):
        """
        Calculates individual sensor confidence levels based on current weather degradation
        and physical hardware health.
        """
        rain = weather_state.get("rain", 0.0) / 100.0
        fog = weather_state.get("fog", 0.0) / 100.0
        dust = weather_state.get("dust", 0.0) / 100.0
        humidity = weather_state.get("humidity", 0.0) / 100.0
        
        # RGB camera degrades severely in fog, heavy rain, and dust
        rgb_env_degrade = max(fog * 0.9, rain * 0.7, dust * 0.85)
        rgb_conf = max(0.05, 1.0 - rgb_env_degrade) * hardware_healths.get("rgb", 1.0)
        
        # Thermal camera is affected by humidity/water vapor absorption and thick fog,
        # but is resilient to dust and moderate light conditions.
        thermal_env_degrade = (fog * humidity * 0.4) + (rain * 0.25)
        thermal_conf = max(0.15, 1.0 - thermal_env_degrade) * hardware_healths.get("thermal", 1.0)
        
        # Radar is highly robust. Rain causes minor backscatter noise.
        radar_env_degrade = rain * 0.10
        radar_conf = max(0.30, 1.0 - radar_env_degrade) * hardware_healths.get("radar", 1.0)
        
        return {
            "rgb": round(rgb_conf, 3),
            "thermal": round(thermal_conf, 3),
            "radar": round(radar_conf, 3)
        }

    @staticmethod
    def fuse_sensors(rgb_detections, thermal_detections, radar_detections, weather_state, hardware_healths):
        """
        Fuses target lists from RGB, Thermal, and Radar.
        Returns fused objects and overall perception confidence.
        """
        confidences = SensorFusion.calculate_sensor_confidences(weather_state, hardware_healths)
        
        # Normalize weights based on confidence
        total_conf = sum(confidences.values())
        if total_conf > 0:
            weights = {k: v / total_conf for k, v in confidences.items()}
        else:
            weights = {"rgb": 0.33, "thermal": 0.33, "radar": 0.34}
            
        overall_perception_conf = sum(confidences.values()) / 3.0
        
        fused_objects = []
        
        # Cluster detections by distance (simple 1D grouping for mock/simulated targets)
        all_targets = []
        for d in rgb_detections:
            all_targets.append({"source": "rgb", "type": d.get("type"), "distance": d.get("distance"), "conf": d.get("confidence")})
        for d in thermal_detections:
            all_targets.append({"source": "thermal", "type": d.get("type"), "distance": d.get("distance"), "conf": d.get("confidence")})
        for d in radar_detections:
            all_targets.append({"source": "radar", "type": d.get("type"), "distance": d.get("distance"), "conf": d.get("confidence")})
            
        # Match targets that are close in distance (within 3.0 meters threshold)
        matched_groups = []
        for target in all_targets:
            added = False
            for group in matched_groups:
                # Calculate mean distance of group
                mean_dist = sum(t["distance"] for t in group) / len(group)
                if abs(target["distance"] - mean_dist) <= 3.5:
                    group.append(target)
                    added = True
                    break
            if not added:
                matched_groups.append([target])
                
        # Build fused objects from groups
        for idx, group in enumerate(matched_groups):
            has_rgb = any(t["source"] == "rgb" for t in group)
            has_thermal = any(t["source"] == "thermal" for t in group)
            has_radar = any(t["source"] == "radar" for t in group)
            
            # Distance: Radar is most accurate, followed by Thermal, then RGB
            radar_target = next((t for t in group if t["source"] == "radar"), None)
            thermal_target = next((t for t in group if t["source"] == "thermal"), None)
            rgb_target = next((t for t in group if t["source"] == "rgb"), None)
            
            if radar_target:
                fused_distance = radar_target["distance"]
            elif thermal_target:
                fused_distance = thermal_target["distance"]
            else:
                fused_distance = rgb_target["distance"]
                
            # Class: Combine naming clues. RGB is best at classification.
            # If RGB not available, Thermal can distinguish Person vs Vehicle (heat signature shape).
            # Radar gives generic 'obstacle' unless fused.
            object_type = "Obstacle"
            if rgb_target and rgb_target["type"] != "Obstacle":
                object_type = rgb_target["type"]
            elif thermal_target and thermal_target["type"] != "Obstacle":
                object_type = thermal_target["type"]
                
            # Calculate combined confidence
            # Multi-sensor agreement increases confidence:
            # C = 1 - PROD(1 - C_i * w_i)
            conf_terms = []
            if rgb_target:
                conf_terms.append(rgb_target["conf"] * confidences["rgb"])
            if thermal_target:
                conf_terms.append(thermal_target["conf"] * confidences["thermal"])
            if radar_target:
                conf_terms.append(radar_target["conf"] * confidences["radar"])
                
            if conf_terms:
                # Combined probability formula (noisy-OR style or weighted average)
                # Let's do a weighted confidence plus an agreement bonus
                weighted_conf = sum(conf_terms) / sum(weights[t["source"]] for t in group)
                agreement_bonus = 0.05 * (len(group) - 1)
                fused_conf = min(0.99, weighted_conf + agreement_bonus)
            else:
                fused_conf = 0.50
                
            fused_objects.append({
                "id": f"OBJ-{idx+1:02d}",
                "type": object_type,
                "distance": round(fused_distance, 1),
                "confidence": round(fused_conf, 2),
                "sensors": {
                    "rgb": has_rgb,
                    "thermal": has_thermal,
                    "radar": has_radar
                }
            })
            
        return fused_objects, round(overall_perception_conf, 3), confidences

// --- MINEGUARD AI - HARDWARE SENSOR FEEDS SIMULATOR RENDERER ---

class SensorFeedRenderer {
    constructor() {
        this.radarSweepAngle = 0;
        this.radarSweepDir = 1;
    }

    render(vehicleId, state) {
        const vehicle = state.vehicles.find(v => v.id === vehicleId);
        if (!vehicle) return;

        const weather = state.weather;
        const visibility = state.visibility_m;

        // Render individual feeds
        this.renderRGBFeed("canvas-sensor-rgb", vehicle, weather, visibility);
        this.renderThermalFeed("canvas-sensor-thermal", vehicle, weather);
        this.renderRadarFeed("canvas-sensor-radar", vehicle);
    }

    renderRGBFeed(canvasId, vehicle, weather, visibility) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;

        ctx.save();
        ctx.clearRect(0, 0, w, h);

        // Apply HTML5 canvas CSS filter to blur image based on weather fog density
        const fogVal = weather.fog || 0;
        const blurAmt = Math.min(12, (fogVal / 100.0) * 8.5);
        if (blurAmt > 0.5) {
            ctx.filter = `blur(${blurAmt.toFixed(1)}px)`;
        }

        // Draw sky horizon & ground perspective lines
        ctx.fillStyle = "#1e293b"; // slate sky
        ctx.fillRect(0, 0, w, h / 2);
        ctx.fillStyle = "#5c4033"; // muddy dirt road ground
        ctx.fillRect(0, h / 2, w, h / 2);

        // Perspective Road margins
        ctx.beginPath();
        ctx.moveTo(w / 2 - 15, h / 2);
        ctx.lineTo(w / 2 + 15, h / 2);
        ctx.lineTo(w - 20, h);
        ctx.lineTo(20, h);
        ctx.closePath();
        ctx.fillStyle = "#483c32"; // gravel road center
        ctx.fill();

        // Draw targets if camera is not mud-occluded
        const isOccluded = vehicle.sensor_health.rgb < 0.15;
        const rgbDets = vehicle.raw_detections ? vehicle.raw_detections.rgb : [];

        if (!isOccluded && rgbDets.length > 0) {
            rgbDets.forEach((det, idx) => {
                // Map range to height offset (close objects are large and low, far objects are small and high)
                const rangeScale = Math.max(0.1, 1.0 - (det.distance / 80.0));
                const objW = 55 * rangeScale;
                const objH = 45 * rangeScale;
                const objX = w / 2 - objW / 2 + (idx * 45 - 20) * rangeScale;
                const objY = h / 2 + (h / 2) * (det.distance / 80.0) - objH;

                // Draw bounding box
                ctx.strokeStyle = "#10b981"; // green box
                ctx.lineWidth = 1.5;
                ctx.strokeRect(objX, objY, objW, objH);

                // Label tag
                ctx.fillStyle = "#10b981";
                ctx.font = `${Math.max(8, Math.round(9 * rangeScale))}px monospace`;
                ctx.fillText(
                    `${det.type} [${Math.round(det.confidence*100)}%]`, 
                    objX, 
                    objY - 4
                );
            });
        }

        ctx.restore(); // Clears blur filter for static overlays

        // Draw camera water drop splash if heavy rain is active
        if (weather.rain > 30.0) {
            ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
            ctx.lineWidth = 1.5;
            for (let i = 0; i < 5; i++) {
                ctx.beginPath();
                ctx.arc(45 + i * 65, 80 + i * 25, 4 + i * 2, 0, Math.PI, true);
                ctx.stroke();
            }
        }

        // Draw mud occlusion overlay if active
        if (isOccluded) {
            ctx.fillStyle = "rgba(101, 67, 33, 0.95)";
            ctx.fillRect(10, 10, w - 20, h - 20);
            ctx.fillStyle = "white";
            ctx.font = "12px 'Share Tech Mono', monospace";
            ctx.textAlign = "center";
            ctx.fillText("📷 RGB CAMERA LENS OCCLUDED", w / 2, h / 2);
            ctx.textAlign = "left";
        }
    }

    renderThermalFeed(canvasId, vehicle, weather) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;

        ctx.clearRect(0, 0, w, h);

        // Cold thermal background (dark violet/deep indigo)
        ctx.fillStyle = "#0c051a";
        ctx.fillRect(0, 0, w, h);

        // Draw cold wireframe perspective lines
        ctx.strokeStyle = "rgba(59, 130, 246, 0.15)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(w / 2, h / 2); ctx.lineTo(0, h);
        ctx.moveTo(w / 2, h / 2); ctx.lineTo(w, h);
        ctx.stroke();

        const isOccluded = vehicle.sensor_health.thermal < 0.15;
        const thermDets = vehicle.raw_detections ? vehicle.raw_detections.thermal : [];

        if (!isOccluded && thermDets.length > 0) {
            thermDets.forEach((det, idx) => {
                const rangeScale = Math.max(0.1, 1.0 - (det.distance / 80.0));
                const objW = 50 * rangeScale;
                const objH = 40 * rangeScale;
                const objX = w / 2 - objW / 2 + (idx * 45 - 20) * rangeScale;
                const objY = h / 2 + (h / 2) * (det.distance / 80.0) - objH;

                // Create thermal glowing heat gradient blob (white hot engine core, yellow body, orange boundary)
                const grad = ctx.createRadialGradient(
                    objX + objW / 2, objY + objH / 2, 1,
                    objX + objW / 2, objY + objH / 2, objW / 2
                );
                
                // Thermal Hotspot Colors
                grad.addColorStop(0, '#ffffff'); // white hot core
                grad.addColorStop(0.2, '#ffea00'); // yellow glow
                grad.addColorStop(0.5, '#ff6a00'); // orange heat
                grad.addColorStop(1, 'rgba(255, 0, 0, 0)'); // fade out to ambient cold

                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.ellipse(
                    objX + objW / 2, 
                    objY + objH / 2, 
                    objW / 2, 
                    objH / 2, 
                    0, 0, 2 * Math.PI
                );
                ctx.fill();

                // Draw bounding box label
                ctx.fillStyle = "#ff6a00";
                ctx.font = `${Math.max(8, Math.round(9 * rangeScale))}px monospace`;
                ctx.fillText(
                    `HEAT: ${Math.round(det.distance)}m [${Math.round(det.confidence*100)}%]`, 
                    objX, 
                    objY - 4
                );
            });
        }

        // Draw thermal mud block alert
        if (isOccluded) {
            ctx.fillStyle = "rgba(22, 15, 40, 0.95)";
            ctx.fillRect(10, 10, w - 20, h - 20);
            ctx.fillStyle = "#ef4444";
            ctx.font = "12px 'Share Tech Mono', monospace";
            ctx.textAlign = "center";
            ctx.fillText("🌡️ THERMAL SENSOR FAULT / BLOCKED", w / 2, h / 2);
            ctx.textAlign = "left";
        }
    }

    renderRadarFeed(canvasId, vehicle) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;

        ctx.clearRect(0, 0, w, h);

        // Dark radar display scope
        ctx.fillStyle = "#030704";
        ctx.fillRect(0, 0, w, h);

        const centerX = w / 2;
        const centerY = h - 20;
        const maxRadius = w / 2 - 20;

        // Draw concentric distance arcs (20m, 40m, 60m, 80m)
        ctx.strokeStyle = "#1b4d24";
        ctx.lineWidth = 1;
        for (let i = 1; i <= 4; i++) {
            const rad = maxRadius * (i / 4.0);
            ctx.beginPath();
            ctx.arc(centerX, centerY, rad, Math.PI, 2 * Math.PI);
            ctx.stroke();

            // Arc labels
            ctx.fillStyle = "#10b981";
            ctx.font = "7px 'Share Tech Mono', monospace";
            ctx.fillText(`${i * 20}m`, centerX + rad - 12, centerY - 4);
        }

        // Radar grid radial angle lines
        const angles = [30, 60, 90, 120, 150];
        angles.forEach(deg => {
            const rad = deg * Math.PI / 180;
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.lineTo(centerX - maxRadius * Math.cos(rad), centerY - maxRadius * Math.sin(rad));
            ctx.stroke();
        });

        const isOccluded = vehicle.sensor_health.radar < 0.15;
        const radarDets = vehicle.raw_detections ? vehicle.raw_detections.radar : [];

        // Update Radar Sweeper radial sweep arm
        this.radarSweepAngle += 2.8 * this.radarSweepDir;
        if (this.radarSweepAngle >= 75) {
            this.radarSweepAngle = 75;
            this.radarSweepDir = -1;
        } else if (this.radarSweepAngle <= -75) {
            this.radarSweepAngle = -75;
            this.radarSweepDir = 1;
        }

        const sweepRad = (90 + this.radarSweepAngle) * Math.PI / 180;

        // Render target returns as radar blips
        if (!isOccluded && radarDets.length > 0) {
            radarDets.forEach(det => {
                // Map range to radial coordinate
                const distRatio = det.distance / 80.0;
                const r = maxRadius * distRatio;
                
                // Spread objects horizontally in mock display angle
                // Mock angles based on target ID to keep them in stable positions
                let degOffset = 0;
                if (det.id.includes("V-02")) degOffset = -22;
                else if (det.id.includes("W-04")) degOffset = 18;
                else if (det.id.includes("BOULDER")) degOffset = -5;

                const targetRad = (90 + degOffset) * Math.PI / 180;
                const targetX = centerX + r * Math.cos(targetRad);
                const targetY = centerY - r * Math.sin(targetRad);

                // Draw glowing radar blip dot
                ctx.beginPath();
                ctx.arc(targetX, targetY, 4, 0, 2 * Math.PI);
                ctx.fillStyle = "rgba(239, 68, 68, 0.85)"; // bright red blip
                ctx.shadowColor = "#ef4444";
                ctx.shadowBlur = 8;
                ctx.fill();
                ctx.shadowBlur = 0; // reset

                // Draw velocity vector line
                ctx.beginPath();
                ctx.moveTo(targetX, targetY);
                // Vector length matches closing speed
                const vecLen = det.relative_speed * 1.5;
                ctx.lineTo(targetX, targetY - vecLen);
                ctx.strokeStyle = "#ff4500";
                ctx.lineWidth = 1.5;
                ctx.stroke();

                // Blip annotation labels
                ctx.fillStyle = "#10b981";
                ctx.font = "8px 'Share Tech Mono', monospace";
                ctx.fillText(
                    `TGT:${det.distance.toFixed(1)}m v:${det.relative_speed > 0 ? '+' : ''}${det.relative_speed}m/s`, 
                    targetX + 8, 
                    targetY - 2
                );
            });
        }

        // Draw sweeping radial arm beam
        ctx.strokeStyle = "rgba(16, 185, 129, 0.4)";
        ctx.lineWidth = 2.0;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(centerX + maxRadius * Math.cos(sweepRad), centerY - maxRadius * Math.sin(sweepRad));
        ctx.stroke();

        // Draw RADAR fault block warning
        if (isOccluded) {
            ctx.fillStyle = "rgba(3, 10, 4, 0.95)";
            ctx.fillRect(10, 10, w - 20, h - 20);
            ctx.fillStyle = "#ef4444";
            ctx.font = "12px 'Share Tech Mono', monospace";
            ctx.textAlign = "center";
            ctx.fillText("📡 RADAR RFI INTERFERENCE / FAULT", w / 2, h / 2);
            ctx.textAlign = "left";
        }
    }
}

window.sensorFeedRenderer = new SensorFeedRenderer();

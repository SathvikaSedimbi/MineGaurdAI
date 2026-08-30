// --- MINEGUARD AI - INTERACTIVE CANVAS MAP RENDERER ---

class MineMapRenderer {
    constructor() {
        this.scale = 1.0;
        this.offsetX = 0.0;
        this.offsetY = 0.0;
        
        // Render layers toggles
        this.rainActive = true;
        this.scannersActive = true;
        
        // Rain particles cache
        this.rainParticles = [];
        for (let i = 0; i < 60; i++) {
            this.rainParticles.push({
                x: Math.random() * 800,
                y: Math.random() * 600,
                speed: 15 + Math.random() * 15,
                len: 10 + Math.random() * 10
            });
        }
    }

    zoomIn() {
        this.scale = Math.min(2.5, this.scale + 0.15);
    }

    zoomOut() {
        this.scale = Math.max(0.6, this.scale - 0.15);
    }

    toggleRain() {
        this.rainActive = !this.rainActive;
    }

    toggleScanners() {
        this.scannersActive = !this.scannersActive;
    }

    render(canvasId, state) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;

        // Clear with dark mine theme background
        ctx.fillStyle = "#06090e";
        ctx.fillRect(0, 0, w, h);

        ctx.save();
        // Handle Pan & Zoom transformations
        // Center of canvas transformation scaling
        ctx.translate(w / 2 + this.offsetX, h / 2 + this.offsetY);
        ctx.scale(this.scale, this.scale);
        ctx.translate(-w / 2, -h / 2);

        // 1. Draw Benches (Terraced concentric circles modeling open pit depth)
        this.drawBenches(ctx, state.benches || []);

        // 2. Draw Restricted Zones (Dashed warning circles)
        this.drawRestrictedZones(ctx, state.restricted_zones || []);

        // 3. Draw Roads / Haul road segments
        this.drawHaulRoads(ctx, state.roads, state.nodes, state.active_road_scan);

        // 4. Draw Map Nodes / Intersections
        this.drawMapNodes(ctx, state.nodes);

        // 5. Draw Workers / Safety zones
        this.drawWorkers(ctx, state.workers, state.vehicles);

        // 6. Draw Vehicles / Digital twin nodes
        this.drawVehicles(ctx, state.vehicles, state);

        ctx.restore();

        // 7. Draw Screen-Space Weather Animations (Rain drops & Fog overlays)
        this.drawWeatherEffects(ctx, w, h, state.weather);
    }

    drawBenches(ctx, benches) {
        // NMDC Bailadila iron ore terraces - hematite red and rock grey contours
        benches.forEach((bench, idx) => {
            ctx.beginPath();
            ctx.ellipse(
                bench.center_x, 
                bench.center_y, 
                bench.radius_x, 
                bench.radius_y, 
                0, 0, 2 * Math.PI
            );
            ctx.lineWidth = 2;
            
            // Outer contours are higher (dark slate gray), inner pit bottom is rusty red
            const shade = 10 + idx * 8;
            ctx.strokeStyle = `rgba(180, ${shade + 40}, ${shade}, 0.25)`; // rusty iron ore coloring
            ctx.stroke();

            // Label bench elevation
            ctx.fillStyle = "rgba(156, 163, 175, 0.4)";
            ctx.font = "10px 'Share Tech Mono', monospace";
            ctx.fillText(`${bench.elevation}m EL`, bench.center_x + bench.radius_x - 30, bench.center_y + 4);
        });
    }

    drawRestrictedZones(ctx, zones) {
        zones.forEach(zone => {
            ctx.beginPath();
            ctx.arc(zone.x, zone.y, zone.radius, 0, 2 * Math.PI);
            ctx.lineWidth = 1.5;
            
            // Pulsing color based on alert
            const alpha = 0.15 + 0.05 * Math.sin(Date.now() / 200);
            ctx.fillStyle = zone.danger_level === "CRITICAL" ? `rgba(239, 68, 68, ${alpha})` : `rgba(245, 158, 11, ${alpha})`;
            ctx.strokeStyle = zone.danger_level === "CRITICAL" ? "#ef4444" : "#f59e0b";
            ctx.setLineDash([4, 4]);
            
            ctx.fill();
            ctx.stroke();
            ctx.setLineDash([]); // Reset line dash

            // Text
            ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
            ctx.font = "9px 'Outfit', sans-serif";
            ctx.textAlign = "center";
            ctx.fillText(zone.name, zone.x, zone.y - 2);
            ctx.fillStyle = zone.danger_level === "CRITICAL" ? "#ef4444" : "#f59e0b";
            ctx.fillText("RESTRICTED", zone.x, zone.y + 8);
            ctx.textAlign = "left"; // Reset align
        });
    }

    drawHaulRoads(ctx, roads, nodes, activeScan) {
        roads.forEach(road => {
            const start = nodes.find(n => n.id === road.start_node);
            const end = nodes.find(n => n.id === road.end_node);

            if (!start || !end) return;

            // Determine road line color based on dynamic water/pothole risk
            let strokeColor = "#1e2d3d"; // default charcoal road
            let width = 4;

            if (road.is_blocked) {
                strokeColor = "#ef4444";
                width = 6;
            } else if (road.is_restricted) {
                strokeColor = "#ef4444";
                ctx.setLineDash([3, 3]);
            } else if (road.status === "DANGEROUS") {
                strokeColor = "#ef4444";
                width = 5;
            } else if (road.status === "CAUTION") {
                strokeColor = "#f59e0b";
                width = 4.5;
            } else {
                strokeColor = "#2c3e50";
            }

            // Draw road path line
            ctx.beginPath();
            ctx.moveTo(start.x, start.y);
            ctx.lineTo(end.x, end.y);
            ctx.lineWidth = width;
            ctx.strokeStyle = strokeColor;
            ctx.stroke();
            ctx.setLineDash([]); // Reset

            // If road is blocked, draw a hazard block symbol in the middle
            if (road.is_blocked) {
                const midX = (start.x + end.x) / 2;
                const midY = (start.y + end.y) / 2;
                
                ctx.fillStyle = "#f59e0b";
                ctx.fillRect(midX - 10, midY - 10, 20, 20);
                
                ctx.fillStyle = "black";
                ctx.font = "12px sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText("🚧", midX, midY);
                ctx.textAlign = "left";
                ctx.textBaseline = "alphabetic";
            }

            // If water accumulation is high, draw blue pooling patches
            if (road.water_accumulation >= 0.40) {
                ctx.beginPath();
                const midX = (start.x + end.x) / 2;
                const midY = (start.y + end.y) / 2;
                ctx.arc(midX, midY, 8 + road.water_accumulation * 12, 0, 2 * Math.PI);
                ctx.fillStyle = "rgba(59, 130, 246, 0.25)";
                ctx.fill();
            }

            // If potholes are active, draw surface damage dots
            if (road.potholes > 0) {
                ctx.fillStyle = "rgba(245, 158, 11, 0.7)";
                // Draw up to 3 warning dots
                const dotCount = Math.min(3, road.potholes);
                for (let i = 0; i < dotCount; i++) {
                    const ratio = 0.25 + i * 0.25;
                    const dotX = start.x + (end.x - start.x) * ratio;
                    const dotY = start.y + (end.y - start.y) * ratio;
                    ctx.beginPath();
                    ctx.arc(dotX, dotY, 2, 0, 2 * Math.PI);
                    ctx.fill();
                }
            }

            // Draw animated laser scanning sweep
            if (this.scannersActive && activeScan && activeScan.road_id === road.id) {
                const progress = activeScan.scan_progress / 100.0;
                // Scanner beam moves from start node to end node
                const beamX = start.x + (end.x - start.x) * progress;
                const beamY = start.y + (end.y - start.y) * progress;
                
                ctx.beginPath();
                ctx.arc(beamX, beamY, 12, 0, 2 * Math.PI);
                ctx.fillStyle = "rgba(16, 185, 129, 0.2)";
                ctx.strokeStyle = "#10b981";
                ctx.lineWidth = 1.5;
                ctx.fill();
                ctx.stroke();
            }
        });
    }

    drawMapNodes(ctx, nodes) {
        nodes.forEach(node => {
            // Draw small connector dots for intersections
            ctx.beginPath();
            ctx.arc(node.x, node.y, 4, 0, 2 * Math.PI);
            ctx.fillStyle = "#1e293b";
            ctx.strokeStyle = "#475569";
            ctx.lineWidth = 1;
            ctx.fill();
            ctx.stroke();

            // Label loaders and dumping nodes
            if (node.type === "loading" || node.type === "dumping" || node.type === "workshop" || node.type === "parking") {
                ctx.fillStyle = "#9ca3af";
                ctx.font = "bold 9px 'Outfit', sans-serif";
                ctx.fillText(node.name, node.x - 30, node.y - 10);
            }
        });
    }

    drawWorkers(ctx, workers, vehicles) {
        workers.forEach(w => {
            // Draw worker avatar yellow dot
            ctx.beginPath();
            ctx.arc(w.position.x, w.position.y, 5, 0, 2 * Math.PI);
            ctx.fillStyle = "#f59e0b"; // yellow
            ctx.strokeStyle = "white";
            ctx.lineWidth = 1;
            ctx.fill();
            ctx.stroke();

            // Label worker ID
            ctx.fillStyle = "#9ca3af";
            ctx.font = "8px 'Share Tech Mono', monospace";
            ctx.fillText(w.id, w.position.x - 10, w.position.y - 8);

            // Draw warning zone if a vehicle is too close to this worker (danger range is 30m / 30px)
            let vehicleClose = false;
            vehicles.forEach(v => {
                const dist = Math.sqrt((v.position.x - w.position.x)**2 + (v.position.y - w.position.y)**2);
                if (dist < 30.0) vehicleClose = true;
            });

            if (vehicleClose) {
                ctx.beginPath();
                ctx.arc(w.position.x, w.position.y, 16, 0, 2 * Math.PI);
                const alpha = 0.2 + 0.1 * Math.sin(Date.now() / 150);
                ctx.strokeStyle = `rgba(239, 68, 68, ${alpha})`;
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }
        });
    }

    drawVehicles(ctx, vehicles, state) {
        vehicles.forEach(v => {
            const x = v.position.x;
            const y = v.position.y;
            const headingRad = Math.radians(v.heading || 0);

            // Determine vehicle avatar glow color based on safety state / priority
            let color = "#3b82f6"; // blue
            if (v.priority === "EMERGENCY") color = "#3b82f6";
            if (v.safety_state === "CRITICAL") color = "#ef4444"; // red
            else if (v.safety_state === "HIGH RISK" || v.safety_state === "CAUTION") color = "#f59e0b"; // orange

            // Draw selected vehicle communication V2V range (500m)
            const selectedId = window.currentSelectedTwin || window.currentSelectedMapVeh;
            if (selectedId && v.id === selectedId) {
                ctx.beginPath();
                ctx.arc(x, y, 500, 0, 2 * Math.PI);
                ctx.strokeStyle = "rgba(59, 130, 246, 0.12)";
                ctx.lineWidth = 1;
                ctx.setLineDash([5, 5]);
                ctx.stroke();
                ctx.setLineDash([]); // reset
                
                ctx.fillStyle = "rgba(59, 130, 246, 0.015)";
                ctx.fill();
            }

            // Draw Emergency route line if emergency vehicle
            if (v.priority === "EMERGENCY" && v.route) {
                ctx.beginPath();
                ctx.moveTo(x, y);
                for (let k = v.route_index + 1; k < v.route.length; k++) {
                    const nodeData = state.nodes.find(n => n.id === v.route[k]);
                    if (nodeData) {
                        ctx.lineTo(nodeData.x, nodeData.y);
                    }
                }
                ctx.strokeStyle = "rgba(59, 130, 246, 0.4)";
                ctx.lineWidth = 2;
                ctx.setLineDash([2, 2]);
                ctx.stroke();
                ctx.setLineDash([]); // reset
            }

            // Draw safety/position glow ring
            ctx.beginPath();
            ctx.arc(x, y, 11, 0, 2 * Math.PI);
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.5;
            ctx.stroke();
            
            ctx.fillStyle = `rgba(${color === "#ef4444" ? "239,68,68" : (color === "#f59e0b" ? "245,158,11" : "59,130,246")}, 0.15)`;
            ctx.fill();

            // Determine vehicle emoji icon
            let icon = "🚛";
            if (v.type === "Ambulance") icon = "🚑";
            else if (v.type === "Rescue Vehicle" || v.type === "Emergency Vehicle") icon = "🚒";
            else if (v.type === "Service Vehicle" || v.type === "Maintenance Vehicle" || v.type === "Service" || v.type === "Water Tanker" || v.type === "Tanker") icon = "🚐";

            // Draw icon inside ring (rotated based on heading)
            ctx.save();
            ctx.translate(x, y);
            ctx.rotate(headingRad);
            ctx.font = "11px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(icon, 0, 0);
            ctx.restore();

            // Label vehicle details (above avatar, not rotated)
            ctx.fillStyle = "white";
            ctx.font = "bold 9px 'Share Tech Mono', monospace";
            ctx.fillText(v.id, x - 12, y - 15);
            
            ctx.fillStyle = "rgba(156, 163, 175, 0.8)";
            ctx.font = "8px 'Share Tech Mono', monospace";
            ctx.fillText(`${Math.round(v.speed_kmh)} km/h`, x - 18, y + 20);

            // Draw link status warning if degraded
            if (v.communicationStatus === "DEGRADED") {
                ctx.fillStyle = "#ef4444";
                ctx.font = "bold 8px sans-serif";
                ctx.fillText("⚠️ NO COMM", x - 22, y - 24);
            }
        });
    }

    drawWeatherEffects(ctx, w, h, weather) {
        if (!weather) return;

        // 1. Draw thick fog overlay (soft white visual overlay depending on fog percentage)
        if (weather.fog > 10.0) {
            const fogAlpha = (weather.fog / 100.0) * 0.45;
            ctx.fillStyle = `rgba(18, 26, 39, ${fogAlpha})`; // navy/white blend matching dark theme
            ctx.fillRect(0, 0, w, h);
        }

        // 2. Draw animated heavy rain particles
        if (this.rainActive && weather.rain > 5.0) {
            const density = Math.round(weather.rain / 100.0 * this.rainParticles.length);
            
            ctx.strokeStyle = "rgba(174, 207, 238, 0.3)";
            ctx.lineWidth = 1;
            
            for (let i = 0; i < density; i++) {
                const p = this.rainParticles[i];
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(p.x - 2, p.y + p.len); // diagonal sweep representing wind blown rain
                ctx.stroke();

                // Update position
                p.y += p.speed;
                p.x -= 0.5; // slight horizontal blow
                
                // Wrap around edges
                if (p.y > h) {
                    p.y = -p.len;
                    p.x = Math.random() * w;
                }
            }
        }
    }
}

// Utility Math
Math.radians = function(degrees) {
    return degrees * Math.PI / 180;
};

Math.degrees = function(radians) {
    return radians * 180 / Math.PI;
};

// Bind to window global instance
window.mineMapRenderer = new MineMapRenderer();

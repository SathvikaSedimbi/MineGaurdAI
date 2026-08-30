// --- MINEGUARD AI - CLIENT STATE MANAGER ---

let simData = null;
let activeView = "view-dashboard";
let isDraggingMap = false;
let startDragOffset = { x: 0, y: 0 };
let currentSelectedTwin = "V-01";
let currentSelectedSensorVeh = "V-01";

// Chart.js Object References
let chartSpeed = null;
let chartVisibility = null;
let chartRisk = null;
let chartTTC = null;

document.addEventListener("DOMContentLoaded", () => {
    // 1. Initialize Sidebar Navigation
    initNavigation();
    
    // 2. Initialize Control Room & Map zoom mouse bindings
    initMapInteractions();

    // 3. Initialize Control Button Handlers
    initControlButtons();

    // 4. Initialize Preset Sliders & Manual Inputs
    initWeatherSliders();

    // 5. Initialize Diagnostic Toggles
    initSensorDiagnostics();
    
    // 5.5. Initialize Review-2 modal and click bindings
    initReview2Controls();

    // 6. Start high frequency polling loop (3Hz / every 333ms)
    startStateSync();
});

// Navigation logic (Single Page Application Switcher)
function initNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    const views = document.querySelectorAll(".content-view");
    const viewTitle = document.getElementById("view-title");

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            // Remove active status
            navItems.forEach(i => i.classList.remove("active"));
            views.forEach(v => v.classList.remove("active"));

            // Set active
            item.classList.add("active");
            activeView = item.getAttribute("data-view");
            const targetViewEl = document.getElementById(activeView);
            if (targetViewEl) {
                targetViewEl.classList.add("active");
            }

            // Update title
            viewTitle.textContent = item.querySelector("span").textContent;

            // Trigger immediate chart resize on tab transition to avoid drawing bugs
            if (activeView === "view-analytics" || activeView === "view-collision") {
                setTimeout(resizeCharts, 50);
            }
        });
    });
}

function initMapInteractions() {
    // Map control buttons
    document.getElementById("btn-map-zoom-in").addEventListener("click", () => {
        window.mineMapRenderer.zoomIn();
    });
    document.getElementById("btn-map-zoom-out").addEventListener("click", () => {
        window.mineMapRenderer.zoomOut();
    });
    document.getElementById("btn-toggle-rain-effect").addEventListener("click", (e) => {
        e.target.classList.toggle("active");
        window.mineMapRenderer.toggleRain();
    });
    document.getElementById("btn-toggle-scan-beam").addEventListener("click", (e) => {
        e.target.classList.toggle("active");
        window.mineMapRenderer.toggleScanners();
    });
}

function initControlButtons() {
    const btnToggle = document.getElementById("btn-sim-toggle");
    const btnReset = document.getElementById("btn-sim-reset");

    btnToggle.addEventListener("click", () => {
        const running = btnToggle.classList.contains("play"); // If is displaying 'Pause'
        const action = running ? "resume" : "pause";
        
        fetch("/api/simulation/control", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: action })
        })
        .then(res => res.json())
        .then(data => {
            if (data.running) {
                btnToggle.textContent = "Pause";
                btnToggle.classList.remove("play");
            } else {
                btnToggle.textContent = "Resume";
                btnToggle.classList.add("play");
            }
        });
    });

    btnReset.addEventListener("click", () => {
        fetch("/api/simulation/control", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "reset" })
        })
        .then(() => {
            btnToggle.textContent = "Pause";
            btnToggle.classList.remove("play");
            console.log("Simulation state reset complete.");
        });
    });

    // Twin select dropdown
    document.getElementById("select-twin-vehicle").addEventListener("change", (e) => {
        currentSelectedTwin = e.target.value;
    });

    // Sensor select dropdown
    document.getElementById("select-sensor-vehicle").addEventListener("change", (e) => {
        currentSelectedSensorVeh = e.target.value;
        // reset checkmarks on change
        document.getElementById("chk-fail-rgb").checked = false;
        document.getElementById("chk-fail-thermal").checked = false;
        document.getElementById("chk-fail-radar").checked = false;
    });

    // Road Scan Button
    document.getElementById("btn-trigger-road-scan").addEventListener("click", () => {
        const roadId = document.getElementById("select-scan-road").value;
        fetch("/api/simulation/road-scan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ road_id: roadId })
        });
    });
}

function initWeatherSliders() {
    const sliders = ["rain", "fog", "wind", "dust", "humidity", "clouds"];
    
    sliders.forEach(key => {
        const slider = document.getElementById(`slider-${key}`);
        const label = document.getElementById(`val-slider-${key}`);
        
        slider.addEventListener("input", () => {
            // Update labels
            if (key === "wind") {
                label.textContent = `${slider.value} km/h`;
            } else {
                label.textContent = `${slider.value}%`;
            }
            
            // Send payload to backend
            const payload = {};
            sliders.forEach(k => {
                payload[k] = document.getElementById(`slider-${k}`).value;
            });
            
            fetch("/api/simulation/weather", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        });
    });
}

function initSensorDiagnostics() {
    const checkRGB = document.getElementById("chk-fail-rgb");
    const checkThermal = document.getElementById("chk-fail-thermal");
    const checkRadar = document.getElementById("chk-fail-radar");

    const sendFailState = (sensor, isFailed) => {
        fetch("/api/simulation/sensor-fail", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                vehicle_id: currentSelectedSensorVeh,
                sensor: sensor,
                failed: isFailed
            })
        });
    };

    checkRGB.addEventListener("change", () => sendFailState("rgb", checkRGB.checked));
    checkThermal.addEventListener("change", () => sendFailState("thermal", checkThermal.checked));
    checkRadar.addEventListener("change", () => sendFailState("radar", checkRadar.checked));

    // Diagnostic window controls
    document.getElementById("btn-trigger-jet-spray").addEventListener("click", (e) => {
        const originalText = e.target.textContent;
        e.target.textContent = "WASH JET ACTIVE... SPRAYING";
        e.target.disabled = true;
        setTimeout(() => {
            e.target.textContent = originalText;
            e.target.disabled = false;
            // Clean failures
            checkRGB.checked = false;
            checkThermal.checked = false;
            sendFailState("rgb", false);
            sendFailState("thermal", false);
        }, 3000);
    });

    document.getElementById("btn-trigger-lens-heater").addEventListener("click", (e) => {
        e.target.classList.toggle("active");
        const active = e.target.classList.contains("active");
        e.target.textContent = active ? "Heater: ON (DEFOGGING)" : "Toggle Optical Window Heater";
    });
}

// Fetch loop
function startStateSync() {
    setInterval(() => {
        fetch("/api/state")
        .then(res => res.json())
        .then(state => {
            simData = state;
            updateGlobalUI();
        })
        .catch(err => console.error("API Connection failure: ", err));
    }, 333);
}

function updateGlobalUI() {
    if (!simData) return;

    // Update global clock
    document.getElementById("lbl-sim-time").textContent = `${simData.simulation_time.toFixed(1)}s`;

    // Render Canvas Maps
    if (activeView === "view-control-room") {
        window.mineMapRenderer.render("canvas-control-room-map", simData);
    } else if (activeView === "view-mine-map") {
        window.mineMapRenderer.render("canvas-full-map", simData);
    }

    // Render Feeds on Sensor tab
    if (activeView === "view-sensor-lab") {
        window.sensorFeedRenderer.render(currentSelectedSensorVeh, simData);
    }

    // Update specific panels based on view selection (performance optimization)
    updateDashboard();
    updateControlRoom();
    updateDigitalTwin();
    updateWeatherUI();
    updateRoadHealthUI();
    updateCollisionUI();
    updateScenariosUI();
    updateAnalyticsUI();
    updateHardwareUI();
    
    // --- REVIEW-2 DYNAMIC UPDATES ---
    updateSidebarFleet();
    updateDashboardReview2();
    updateMapDetailsPopup();
}

// VIEW UPDATERS
function updateDashboard() {
    // Set metric badges
    document.getElementById("dash-visibility-val").textContent = `${simData.visibility_m.toFixed(1)}m`;
    const catEl = document.getElementById("dash-visibility-cat");
    catEl.textContent = simData.visibility_category;
    
    // Switch class for warning indicator colors
    catEl.className = "badge";
    if (simData.visibility_category === "CLEAR") catEl.classList.add("badge-success");
    else if (simData.visibility_category === "LIGHT FOG") catEl.classList.add("badge-primary");
    else if (simData.visibility_category === "MODERATE FOG") catEl.classList.add("badge-warning");
    else catEl.classList.add("badge-danger");

    const alertsCount = simData.alerts.length;
    document.getElementById("dash-alerts-val").textContent = alertsCount;
    const alertStat = document.getElementById("dash-alerts-status");
    alertStat.className = "badge";
    if (alertsCount === 0) {
        alertStat.textContent = "NOMINAL";
        alertStat.classList.add("badge-success");
    } else if (simData.alerts.some(a => a.level === "CRITICAL")) {
        alertStat.textContent = "CRITICAL LIMIT";
        alertStat.classList.add("badge-danger");
    } else {
        alertStat.textContent = "WARNING";
        alertStat.classList.add("badge-warning");
    }

    // Efficiency and haul cycle
    document.getElementById("dash-eff-val").textContent = `${simData.fleet_metrics.efficiency}%`;
    document.getElementById("dash-cycle-val").textContent = `${simData.fleet_metrics.haul_cycle_min.toFixed(1)}m`;
    
    // Calculate difference
    const diff = simData.fleet_metrics.haul_cycle_min - 25.0;
    document.getElementById("dash-cycle-diff").textContent = diff > 0 ? `+${diff.toFixed(1)}m delay` : "0.0m delay";

    // Alert Logs list
    const alertList = document.getElementById("dashboard-alert-list");
    if (simData.alerts.length === 0) {
        alertList.innerHTML = `<div class="empty-state">No active warnings. System running normally.</div>`;
    } else {
        alertList.innerHTML = simData.alerts.map(a => `
            <div class="alert-log-item ${a.level}">
                <div class="alert-item-header">
                    <span class="alert-title">${a.title}</span>
                    <span class="alert-time">${a.timestamp}</span>
                </div>
                <p class="alert-desc">${a.explanation}</p>
                <span class="alert-action">RECOMMENDED ACTION: ${a.action}</span>
            </div>
        `).join("");
    }

    // Current weather panel numbers
    document.getElementById("dash-w-rain").textContent = `${Math.round(simData.weather.rain)}%`;
    document.getElementById("dash-w-fog").textContent = `${Math.round(simData.weather.fog)}%`;
    document.getElementById("dash-w-wind").textContent = `${Math.round(simData.weather.wind)} km/h`;
    document.getElementById("dash-w-dust").textContent = `${Math.round(simData.weather.dust)}%`;
    document.getElementById("dash-w-hum").textContent = `${Math.round(simData.weather.humidity)}%`;
    document.getElementById("dash-w-clouds").textContent = `${Math.round(simData.weather.clouds)}%`;
}

function updateControlRoom() {
    if (activeView !== "view-control-room") return;

    // Table body
    const tableBody = document.getElementById("control-fleet-table-body");
    if (tableBody) {
        tableBody.innerHTML = simData.vehicles.map(v => {
            let statusColor = "#10b981"; // green
            let statusText = "SAFE";
            if (v.priority === "EMERGENCY") {
                statusColor = "#3b82f6"; // blue
                statusText = "EMERGENCY";
            } else if (v.safety_state === "CRITICAL") {
                statusColor = "#ef4444"; // red
                statusText = "CRITICAL";
            } else if (v.safety_state === "HIGH RISK" || v.safety_state === "CAUTION") {
                statusColor = "#f59e0b"; // orange
                statusText = "CAUTION";
            }
            
            const icon = v.type === "Ambulance" ? "🚑" : (v.type === "Service Vehicle" ? "🚐" : "🚛");
            const connectionStatus = v.communicationStatus === "DEGRADED" ? " ⚠️ (LOST)" : "";
            
            return `
                <tr onclick="selectTwinVehicle('${v.id}')" style="cursor: pointer;">
                    <td style="padding: 6px 4px; font-weight: bold;">${v.id}</td>
                    <td style="padding: 6px 4px;">${icon} ${v.type}${connectionStatus}</td>
                    <td style="padding: 6px 4px;">${Math.round(v.speed_kmh)} km/h</td>
                    <td style="padding: 6px 4px; color: ${statusColor}; font-weight: bold;">● ${statusText}</td>
                </tr>
            `;
        }).join("");
    }

    // Combined Environmental Threat
    const threatFill = document.getElementById("cr-threat-fill");
    const threatLbl = document.getElementById("cr-threat-lbl");
    const vis = simData.visibility_m;

    let threatPct = 5;
    let labelText = "LOW";
    threatFill.className = "meter-bar-fill";

    if (vis <= 5.0) {
        threatPct = 95;
        labelText = "CRITICAL MONSOON LIMIT";
        threatFill.classList.add("bg-danger");
    } else if (vis <= 15.0) {
        threatPct = 75;
        labelText = "HIGH RISK LOW VISIBILITY";
        threatFill.classList.add("bg-danger");
    } else if (vis <= 35.0) {
        threatPct = 40;
        labelText = "CAUTION WEATHER DEGRADED";
        threatFill.classList.add("bg-warning");
    } else {
        threatPct = 10;
        labelText = "NORMAL OPERATIONAL WEATHER";
        threatFill.classList.add("bg-success");
    }
    threatFill.style.width = `${threatPct}%`;
    threatLbl.textContent = labelText;
}

window.selectTwinVehicle = function(id) {
    currentSelectedTwin = id;
    document.getElementById("select-twin-vehicle").value = id;
    // Switch to twin view
    document.querySelector('.nav-item[data-view="view-twin"]').click();
}

function updateDigitalTwin() {
    if (activeView !== "view-twin") return;

    const v = simData.vehicles.find(veh => veh.id === currentSelectedTwin);
    if (!v) return;

    document.getElementById("lbl-twin-name").textContent = `${v.id} — ${v.name} Digital Twin Telemetry`;
    document.getElementById("twin-type").textContent = v.type.toUpperCase();
    document.getElementById("twin-speed").textContent = `${v.speed_kmh} km/h`;
    document.getElementById("twin-rec-speed").textContent = `${v.recommended_speed_kmh} km/h`;
    document.getElementById("twin-heading").textContent = `${v.heading}°`;
    document.getElementById("twin-road").textContent = v.current_road;
    
    const safetyEl = document.getElementById("twin-safety");
    safetyEl.textContent = v.safety_state;
    safetyEl.className = "";
    if (v.safety_state === "NORMAL") safetyEl.classList.add("text-glow-green");
    else if (v.safety_state === "CAUTION") safetyEl.classList.add("text-glow-warning");
    else safetyEl.classList.add("text-glow-red");

    // Sensor bars
    const rgbPct = Math.round(v.sensor_confidence.rgb * 100);
    const thermPct = Math.round(v.sensor_confidence.thermal * 100);
    const radPct = Math.round(v.sensor_confidence.radar * 100);

    document.getElementById("twin-conf-rgb").textContent = `${rgbPct}%`;
    document.getElementById("twin-conf-thermal").textContent = `${thermPct}%`;
    document.getElementById("twin-conf-radar").textContent = `${radPct}%`;

    document.getElementById("twin-bar-rgb").style.width = `${rgbPct}%`;
    document.getElementById("twin-bar-thermal").style.width = `${thermPct}%`;
    document.getElementById("twin-bar-radar").style.width = `${radPct}%`;

    // Bounding boxes fused target list
    const listEl = document.getElementById("twin-object-list");
    if (!v.fused_objects || v.fused_objects.length === 0) {
        listEl.innerHTML = `<div class="empty-state">No obstacles detected in sensor cone.</div>`;
    } else {
        listEl.innerHTML = v.fused_objects.map(obj => `
            <div class="object-node">
                <div class="object-node-left">
                    <span class="object-node-type">${obj.type} (${obj.id})</span>
                    <span class="object-node-dist">Range: ${obj.distance}m</span>
                    <div class="object-node-sensors">
                        <span class="sensor-indicator ${obj.sensors.rgb ? 'active' : ''}">C</span>
                        <span class="sensor-indicator ${obj.sensors.thermal ? 'active' : ''}">T</span>
                        <span class="sensor-indicator ${obj.sensors.radar ? 'active' : ''}">R</span>
                    </div>
                </div>
                <span class="object-node-conf text-glow-green">${Math.round(obj.confidence*100)}%</span>
            </div>
        `).join("");
    }
}

function updateWeatherUI() {
    if (activeView !== "view-weather") return;

    // Calc impact
    document.getElementById("lbl-w-calc-vis").textContent = `${simData.visibility_m.toFixed(1)}m`;
    const catEl = document.getElementById("lbl-w-calc-cat");
    catEl.textContent = simData.visibility_category;
    
    catEl.className = "badge";
    if (simData.visibility_category === "CLEAR") catEl.classList.add("badge-success");
    else if (simData.visibility_category === "LIGHT FOG") catEl.classList.add("badge-primary");
    else if (simData.visibility_category === "MODERATE FOG") catEl.classList.add("badge-warning");
    else catEl.classList.add("badge-danger");

    // Update weights labels
    const v1 = simData.vehicles[0]; // read first vehicle's weights as sample
    if (v1) {
        const rgbPct = Math.round(v1.sensor_confidence.rgb * 100);
        const thermPct = Math.round(v1.sensor_confidence.thermal * 100);
        const radPct = Math.round(v1.sensor_confidence.radar * 100);
        const total = rgbPct + thermPct + radPct;
        
        document.getElementById("lbl-w-weight-rgb").textContent = `${Math.round(rgbPct/total*100)}%`;
        document.getElementById("lbl-w-weight-thermal").textContent = `${Math.round(thermPct/total*100)}%`;
        document.getElementById("lbl-w-weight-radar").textContent = `${Math.round(radPct/total*100)}%`;
    }
}

function updateRoadHealthUI() {
    if (activeView !== "view-road-health") return;

    const tableBody = document.getElementById("table-road-health");
    tableBody.innerHTML = simData.roads.map(road => {
        let flagClass = "text-glow-green";
        if (road.status === "DANGEROUS") flagClass = "text-glow-red";
        else if (road.status === "CAUTION") flagClass = "text-glow-warning";

        return `
            <tr>
                <td><strong>${road.id}</strong></td>
                <td>${road.name}</td>
                <td>${Math.round(road.water_accumulation*100)}%</td>
                <td>${road.potholes}</td>
                <td>${road.slope_deg}°</td>
                <td>${Math.round(road.surface_quality*100)}%</td>
                <td><strong class="${flagClass}">${road.recommended_speed} km/h</strong></td>
                <td><button class="action-btn" onclick="scanRoadSegment('${road.id}')">Scan Laser</button></td>
            </tr>
        `;
    }).join("");

    // Populate dropdown if empty
    const dropdown = document.getElementById("select-scan-road");
    if (dropdown.children.length === 0) {
        dropdown.innerHTML = simData.roads.map(r => `<option value="${r.id}">${r.id} - ${r.name}</option>`).join("");
    }

    // Check dynamic scan progress
    const scan = simData.active_road_scan;
    const scanBox = document.getElementById("box-scan-progress");
    if (scan) {
        scanBox.classList.remove("hidden");
        document.getElementById("lbl-scanning-road-id").textContent = scan.road_id;
        document.getElementById("bar-scan-progress").style.width = `${scan.scan_progress}%`;
        document.getElementById("lbl-scan-progress-val").textContent = `${Math.round(scan.scan_progress)}%`;
        if (scan.complete) {
            document.getElementById("btn-trigger-road-scan").textContent = "Scan complete! Roads Re-calculated";
        } else {
            document.getElementById("btn-trigger-road-scan").textContent = "Laser Sweep active...";
        }
    } else {
        scanBox.classList.add("hidden");
        document.getElementById("btn-trigger-road-scan").textContent = "Trigger Active Road Scan";
    }
}

window.scanRoadSegment = function(roadId) {
    document.getElementById("select-scan-road").value = roadId;
    document.getElementById("btn-trigger-road-scan").click();
}

function updateCollisionUI() {
    if (activeView !== "view-collision") return;

    // Active threats list
    const listEl = document.getElementById("collision-threats-list");
    if (simData.active_conflicts.length === 0) {
        listEl.innerHTML = `<div class="empty-state">No collision paths detected. Safety margins nominal.</div>`;
        document.getElementById("box-risk-explanation").classList.add("hidden");
    } else {
        listEl.innerHTML = simData.active_conflicts.map(c => `
            <div class="object-node" style="border-left: 4px solid var(--color-danger)">
                <div class="object-node-left">
                    <span class="object-node-type">Conflict: ${c.v1} ↔ ${c.v2}</span>
                    <span class="object-node-dist">TTC: ${c.ttc}s | Closing Speed: ${c.closing_speed} m/s</span>
                </div>
                <span class="object-node-conf text-glow-red">${c.distance}m</span>
            </div>
        `).join("");

        // Explanation panel for the worst threat
        const primaryConflict = simData.active_conflicts[0];
        const explainBox = document.getElementById("box-risk-explanation");
        explainBox.classList.remove("hidden");
        
        const worstAlert = simData.alerts.find(a => a.id.includes(primaryConflict.v1) && a.id.includes(primaryConflict.v2));
        if (worstAlert) {
            document.getElementById("lbl-exp-level").textContent = worstAlert.level;
            document.getElementById("lbl-exp-title").textContent = worstAlert.title;
            document.getElementById("lbl-exp-text").textContent = worstAlert.explanation;
            document.getElementById("lbl-exp-action").textContent = worstAlert.action;
        }
    }

    // Chart draw
    drawTTCChart();
}

function updateScenariosUI() {
    if (activeView !== "view-scenarios") return;

    // Load presets if container is empty
    const container = document.getElementById("scenarios-container");
    if (container.children.length === 0 && simData.scenarios_config) {
        container.innerHTML = simData.scenarios_config.map(s => `
            <div class="scenario-card" id="card-scen-${s.id}" onclick="triggerScenario(${s.id})">
                <h4>${s.name}</h4>
                <p>${s.description}</p>
            </div>
        `).join("");
    }

    // Highlights
    if (simData.active_scenario_id) {
        document.querySelectorAll(".scenario-card").forEach(c => c.classList.remove("active"));
        const activeCard = document.getElementById(`card-scen-${simData.active_scenario_id}`);
        if (activeCard) activeCard.classList.add("active");

        const scenConf = simData.scenarios_config.find(s => s.id === simData.active_scenario_id);
        document.getElementById("scen-active-name").textContent = scenConf ? scenConf.name.split(":")[1] : "Active";
        document.getElementById("scen-active-time").textContent = `${simData.scenario_time.toFixed(1)}s`;
    } else {
        document.querySelectorAll(".scenario-card").forEach(c => c.classList.remove("active"));
        document.getElementById("scen-active-name").textContent = "None";
        document.getElementById("scen-active-time").textContent = "0.0s";
    }

    // Log messages
    const logList = document.getElementById("timeline-logs-list");
    if (simData.scenario_logs && simData.scenario_logs.length > 0) {
        logList.innerHTML = simData.scenario_logs.map(log => `<div>${log}</div>`).join("");
        // auto scroll to bottom
        logList.scrollTop = logList.scrollHeight;
    } else {
        logList.innerHTML = `<div class="empty-state">No scenario active. Choose a scenario on the left.</div>`;
    }
}

window.triggerScenario = function(scenId) {
    fetch("/api/simulation/scenario", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: scenId })
    });
}

function updateAnalyticsUI() {
    if (activeView !== "view-analytics") return;
    drawAnalyticsCharts();
}

function updateHardwareUI() {
    if (activeView !== "view-hardware") return;
    // diagnostics values are static or slightly randomized on tick
}

// CHART CONSTRUCTORS
function drawTTCChart() {
    const ctx = document.getElementById("chart-collision-ttc").getContext("2d");
    const hist = simData.analytics_history;
    
    if (chartTTC) {
        chartTTC.data.labels = hist.time;
        // Plot TTC value of V-01 (mock/first conflict for analytics simplicity)
        const v1 = simData.vehicles[0];
        let v1_ttc = 999;
        const activeC = simData.active_conflicts.find(c => c.v1 === "V-01" || c.v2 === "V-01");
        if (activeC) v1_ttc = activeC.ttc;
        
        // Accumulate in mock cache or plot active alerts count
        chartTTC.data.datasets[0].data = hist.alerts_count;
        chartTTC.update();
        return;
    }

    chartTTC = new Chart(ctx, {
        type: 'line',
        data: {
            labels: hist.time,
            datasets: [{
                label: 'Active Critical Warnings',
                data: hist.alerts_count,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.05)',
                borderWidth: 2,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { grid: { color: '#1f2d3d' }, ticks: { color: '#9ca3af' } },
                x: { grid: { color: '#1f2d3d' }, ticks: { color: '#9ca3af' } }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function drawAnalyticsCharts() {
    const hist = simData.analytics_history;
    
    // 1. Speed Chart
    const ctxSpeed = document.getElementById("chart-analytics-speed").getContext("2d");
    if (chartSpeed) {
        chartSpeed.data.labels = hist.time;
        chartSpeed.data.datasets[0].data = hist.avg_speed;
        chartSpeed.update();
    } else {
        chartSpeed = new Chart(ctxSpeed, {
            type: 'line',
            data: {
                labels: hist.time,
                datasets: [{
                    label: 'Avg Fleet Speed (km/h)',
                    data: hist.avg_speed,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.05)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { grid: { color: '#1f2d3d' }, ticks: { color: '#9ca3af' } },
                    x: { grid: { color: '#1f2d3d' }, ticks: { color: '#9ca3af' } }
                }
            }
        });
    }

    // 2. Visibility Chart
    const ctxVis = document.getElementById("chart-analytics-visibility").getContext("2d");
    if (chartVisibility) {
        chartVisibility.data.labels = hist.time;
        chartVisibility.data.datasets[0].data = hist.visibility;
        chartVisibility.update();
    } else {
        chartVisibility = new Chart(ctxVis, {
            type: 'line',
            data: {
                labels: hist.time,
                datasets: [{
                    label: 'Visibility Range (meters)',
                    data: hist.visibility,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.05)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { grid: { color: '#1f2d3d' }, ticks: { color: '#9ca3af' } },
                    x: { grid: { color: '#1f2d3d' }, ticks: { color: '#9ca3af' } }
                }
            }
        });
    }

    // 3. Risk Bar Chart
    const ctxRisk = document.getElementById("chart-analytics-risk").getContext("2d");
    const riskData = [
        hist.risk_distribution.NORMAL,
        hist.risk_distribution.CAUTION,
        hist.risk_distribution.HIGH_RISK,
        hist.risk_distribution.CRITICAL
    ];
    if (chartRisk) {
        chartRisk.data.datasets[0].data = riskData;
        chartRisk.update();
    } else {
        chartRisk = new Chart(ctxRisk, {
            type: 'bar',
            data: {
                labels: ['Normal', 'Caution', 'High Risk', 'Critical'],
                datasets: [{
                    label: 'Vehicles',
                    data: riskData,
                    backgroundColor: ['#10b981', '#f59e0b', '#f59e0b', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { grid: { color: '#1f2d3d' }, ticks: { color: '#9ca3af', stepSize: 1 } },
                    x: { grid: { color: '#1f2d3d' }, ticks: { color: '#9ca3af' } }
                },
                plugins: { legend: { display: false } }
            }
        });
    }
}

function resizeCharts() {
    if (chartSpeed) chartSpeed.resize();
    if (chartVisibility) chartVisibility.resize();
    if (chartRisk) chartRisk.resize();
    if (chartTTC) chartTTC.resize();
}

// --- REVIEW-2 CLIENT ENGINE ---

let currentSelectedMapVeh = null;

function initReview2Controls() {
    const modalAdd = document.getElementById("modal-add-vehicle");
    const modalInc = document.getElementById("modal-report-incident");
    
    document.getElementById("btn-open-add-vehicle-modal").addEventListener("click", () => {
        populateDropdowns();
        modalAdd.style.display = "flex";
    });
    
    document.getElementById("close-add-vehicle-modal").addEventListener("click", () => {
        modalAdd.style.display = "none";
    });
    document.getElementById("btn-cancel-add-vehicle").addEventListener("click", () => {
        modalAdd.style.display = "none";
    });
    
    document.getElementById("btn-open-report-incident-modal").addEventListener("click", () => {
        populateDropdowns();
        modalInc.style.display = "flex";
    });
    
    document.getElementById("close-report-incident-modal").addEventListener("click", () => {
        modalInc.style.display = "none";
    });
    document.getElementById("btn-cancel-report-incident").addEventListener("click", () => {
        modalInc.style.display = "none";
    });
    
    document.getElementById("close-veh-details-btn").addEventListener("click", () => {
        document.getElementById("map-vehicle-details").classList.add("hidden");
        currentSelectedMapVeh = null;
    });
    
    document.getElementById("btn-toggle-veh-conn").addEventListener("click", () => {
        if (!currentSelectedMapVeh) return;
        const detailsConn = document.getElementById("det-veh-conn");
        const action = detailsConn.textContent.trim() === "ONLINE" ? "disconnect" : "reconnect";
        
        fetch("/api/simulation/connectivity", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ vehicle_id: currentSelectedMapVeh, action: action })
        })
        .then(res => res.json())
        .then(data => {
            detailsConn.textContent = data.communicationStatus;
            document.getElementById("btn-toggle-veh-conn").textContent = data.communicationStatus === "ONLINE" ? "Simulate Connection Loss" : "Restore Connection";
        });
    });
    
    document.getElementById("form-add-vehicle").addEventListener("submit", (e) => {
        e.preventDefault();
        const payload = {
            id: document.getElementById("add-veh-id").value,
            type: document.getElementById("add-veh-type").value,
            name: document.getElementById("add-veh-name").value,
            start_node: document.getElementById("add-veh-start").value,
            target_node: document.getElementById("add-veh-dest").value,
            speed: parseFloat(document.getElementById("add-veh-speed").value),
            priority: document.getElementById("add-veh-priority").value
        };
        
        fetch("/api/simulation/add-vehicle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                modalAdd.style.display = "none";
                document.getElementById("form-add-vehicle").reset();
                
                // Add select-twin-vehicle option dynamically
                const selectTwin = document.getElementById("select-twin-vehicle");
                if (!Array.from(selectTwin.options).some(opt => opt.value === payload.id)) {
                    const opt = document.createElement("option");
                    opt.value = payload.id;
                    opt.textContent = `${payload.id} — ${payload.type}`;
                    selectTwin.appendChild(opt);
                }
            } else {
                alert("Error: " + data.message);
            }
        });
    });
    
    document.getElementById("form-report-incident").addEventListener("submit", (e) => {
        e.preventDefault();
        const payload = {
            type: document.getElementById("rep-inc-type").value,
            roadId: document.getElementById("rep-inc-road").value,
            severity: document.getElementById("rep-inc-severity").value
        };
        
        fetch("/api/simulation/report-incident", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                modalInc.style.display = "none";
                document.getElementById("form-report-incident").reset();
            } else {
                alert("Error: " + data.message);
            }
        });
    });
    
    const canvCR = document.getElementById("canvas-control-room-map");
    const canvMap = document.getElementById("canvas-full-map");
    if (canvCR) canvCR.addEventListener("click", (e) => handleCanvasClick(e, "canvas-control-room-map"));
    if (canvMap) canvMap.addEventListener("click", (e) => handleCanvasClick(e, "canvas-full-map"));
}

function populateDropdowns() {
    if (!simData) return;
    
    const startSelect = document.getElementById("add-veh-start");
    const destSelect = document.getElementById("add-veh-dest");
    if (startSelect && startSelect.children.length === 0) {
        simData.nodes.forEach(node => {
            const opt1 = document.createElement("option");
            opt1.value = node.id;
            opt1.textContent = `${node.id} - ${node.name}`;
            startSelect.appendChild(opt1);
            
            const opt2 = document.createElement("option");
            opt2.value = node.id;
            opt2.textContent = `${node.id} - ${node.name}`;
            destSelect.appendChild(opt2);
        });
    }
    
    const roadSelect = document.getElementById("rep-inc-road");
    if (roadSelect && roadSelect.children.length === 0) {
        simData.roads.forEach(road => {
            const opt = document.createElement("option");
            opt.value = road.id;
            opt.textContent = `${road.id} - ${road.name}`;
            roadSelect.appendChild(opt);
        });
    }
}

function handleCanvasClick(e, canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !simData) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;
    
    const renderer = window.mineMapRenderer;
    const w = canvas.width;
    const h = canvas.height;
    
    let tx = clickX - (w / 2 + renderer.offsetX);
    let ty = clickY - (h / 2 + renderer.offsetY);
    
    tx = tx / renderer.scale;
    ty = ty / renderer.scale;
    
    const mapX = tx + w / 2;
    const mapY = ty + h / 2;
    
    let selectedVeh = null;
    simData.vehicles.forEach(v => {
        const dx = v.position.x - mapX;
        const dy = v.position.y - mapY;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist <= 15.0) {
            selectedVeh = v;
        }
    });
    
    if (selectedVeh) {
        openVehicleDetailsCard(selectedVeh);
    } else {
        let selectedNode = null;
        simData.nodes.forEach(n => {
            const dx = n.x - mapX;
            const dy = n.y - mapY;
            const dist = Math.sqrt(dx*dx + dy*dy);
            if (dist <= 12.0) {
                selectedNode = n;
            }
        });
        
        if (selectedNode) {
            const modalAdd = document.getElementById("modal-add-vehicle");
            if (modalAdd && modalAdd.style.display === "flex") {
                const activeField = document.activeElement;
                if (activeField && activeField.id === "add-veh-dest") {
                    document.getElementById("add-veh-dest").value = selectedNode.id;
                } else {
                    document.getElementById("add-veh-start").value = selectedNode.id;
                }
            }
        }
    }
}

function openVehicleDetailsCard(vehicle) {
    currentSelectedMapVeh = vehicle.id;
    
    document.getElementById("det-veh-id").textContent = vehicle.id;
    document.getElementById("det-veh-type").textContent = vehicle.type;
    document.getElementById("det-veh-priority").textContent = vehicle.priority;
    document.getElementById("det-veh-speed").textContent = `${Math.round(vehicle.speed_kmh)} km/h`;
    document.getElementById("det-veh-road").textContent = vehicle.current_road || "N/A";
    document.getElementById("det-veh-dest").textContent = vehicle.target_node || "N/A";
    document.getElementById("det-veh-status").textContent = vehicle.safety_state;
    
    const conn = vehicle.communicationStatus || "ONLINE";
    document.getElementById("det-veh-conn").textContent = conn;
    
    const toggleBtn = document.getElementById("btn-toggle-veh-conn");
    toggleBtn.textContent = conn === "ONLINE" ? "Simulate Connection Loss" : "Restore Connection";
    
    const detailsCard = document.getElementById("map-vehicle-details");
    detailsCard.classList.remove("hidden");
    
    updateDetailsV2V(vehicle);
}

function updateDetailsV2V(vehicle) {
    const nearbyEl = document.getElementById("det-veh-nearby");
    if (!nearbyEl) return;
    
    const nearby = vehicle.nearby_vehicles || [];
    if (nearby.length === 0) {
        nearbyEl.innerHTML = `<div style="color: #9ca3af; font-style: italic;">No vehicles in range.</div>`;
    } else {
        nearbyEl.innerHTML = nearby.map(other => {
            let priorityBadge = "";
            if (other.priority === "EMERGENCY") priorityBadge = " 🚨";
            return `
                <div style="display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.05); padding: 2px 0;">
                    <span>${other.type === "Ambulance" ? "🚑" : (other.type === "Service Vehicle" ? "🚐" : "🚛")} ${other.id}${priorityBadge}</span>
                    <span>${other.distance}m (${other.direction})</span>
                </div>
            `;
        }).join("");
    }
}

function updateSidebarFleet() {
    const sidebarActiveVehicles = document.getElementById("sidebar-active-vehicles");
    if (sidebarActiveVehicles && simData.vehicles) {
        sidebarActiveVehicles.innerHTML = simData.vehicles.map(v => {
            let dotColor = "#10b981";
            if (v.safety_state === "CRITICAL") dotColor = "#ef4444";
            else if (v.safety_state === "HIGH RISK" || v.safety_state === "CAUTION") dotColor = "#f59e0b";
            
            const icon = v.type === "Ambulance" ? "🚑" : (v.type === "Service Vehicle" ? "🚐" : "🚛");
            const connWarning = v.communicationStatus === "DEGRADED" ? " ⚠️ (LOST)" : "";
            
            return `
                <div class="sidebar-vehicle-item" onclick="selectTwinVehicle('${v.id}')">
                    <span class="lbl">${icon} ${v.id}${connWarning}</span>
                    <span class="dot" style="background-color: ${dotColor}"></span>
                </div>
            `;
        }).join("");
    }
    
    const sidebarIncidentStatus = document.getElementById("sidebar-incident-status");
    if (sidebarIncidentStatus && simData.incidents) {
        if (simData.incidents.length === 0) {
            sidebarIncidentStatus.innerHTML = `<div class="empty-state" style="font-size: 10px; color: #9ca3af;">No active incidents.</div>`;
        } else {
            sidebarIncidentStatus.innerHTML = simData.incidents.map(inc => `
                <div class="sidebar-incident-item" style="color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.2);">
                    <span class="lbl" style="color: #ef4444;">⚠ ${inc.type} (${inc.roadId})</span>
                    <span style="font-size: 8px; color: #ef4444; font-weight: bold;">🔴 BLOCKED</span>
                </div>
            `).join("");
        }
    }
}

function updateDashboardReview2() {
    const dashInc = document.getElementById("dashboard-incident-panel");
    if (dashInc && simData.incidents) {
        if (simData.incidents.length === 0) {
            dashInc.innerHTML = `<div class="empty-state">No active road blockages or calamities reported.</div>`;
        } else {
            dashInc.innerHTML = simData.incidents.map(inc => {
                const affected = inc.affectedVehicles.length > 0 ? inc.affectedVehicles.join(", ") : "None";
                const altRoute = inc.alternativeRoute ? inc.alternativeRoute : "Rerouting / Stopped";
                
                const sent = simData.fleet_notifications.sent;
                const delivered = simData.fleet_notifications.delivered;
                const ack = simData.fleet_notifications.acknowledged;
                const pend = simData.fleet_notifications.pending;
                
                return `
                    <div class="incident-card-item" style="margin-bottom: 8px;">
                        <div style="font-size: 20px; align-self: start;">🚧</div>
                        <div class="incident-info-box">
                            <strong style="font-family: 'Share Tech Mono', monospace; font-size: 13px; color: #ef4444;">${inc.type.toUpperCase()} ON ROAD ${inc.roadId}</strong>
                            <span style="font-size: 10px;">Severity: <strong style="color:#ef4444;">${inc.severity}</strong> | Registered: ${inc.timestamp}</span>
                            <span style="font-size: 10px;">Approaching / Affected Fleet: <strong style="color: #f59e0b;">${affected}</strong></span>
                            <span style="font-size: 10px;">Alternative Safe Path: <strong style="color: #10b981;">${altRoute}</strong></span>
                        </div>
                        <div class="incident-actions-box" style="font-size: 9px; font-family: monospace; display: flex; flex-direction: column; align-items: flex-end; background: rgba(0,0,0,0.3); padding: 4px; border-radius: 3px; border: 1px solid var(--border-color);">
                            <div>Sent: <strong>${sent}</strong></div>
                            <div>Deliv: <strong>${delivered}</strong></div>
                            <div>Ack: <strong>${ack}</strong></div>
                            <div>Pend: <strong>${pend}</strong></div>
                        </div>
                    </div>
                `;
            }).join("");
        }
    }
    
    const dashTimeline = document.getElementById("dashboard-timeline-list");
    if (dashTimeline && simData.timeline) {
        if (simData.timeline.length === 0) {
            dashTimeline.innerHTML = `<div class="empty-state">No timeline events recorded.</div>`;
        } else {
            dashTimeline.innerHTML = simData.timeline.map(log => `
                <div style="padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.03); line-height: 1.3;">
                    <span style="color: #10b981; font-weight: bold;">[${log.time}]</span> ${log.message}
                </div>
            `).join("");
            dashTimeline.scrollTop = dashTimeline.scrollHeight;
        }
    }
}

function updateMapDetailsPopup() {
    if (currentSelectedMapVeh) {
        const v = simData.vehicles.find(veh => veh.id === currentSelectedMapVeh);
        if (v) {
            document.getElementById("det-veh-speed").textContent = `${Math.round(v.speed_kmh)} km/h`;
            document.getElementById("det-veh-road").textContent = v.current_road || v.current_node || "N/A";
            document.getElementById("det-veh-status").textContent = v.safety_state;
            document.getElementById("det-veh-conn").textContent = v.communicationStatus || "ONLINE";
            updateDetailsV2V(v);
        }
    }
}

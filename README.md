# MineGuard AI — Intelligent Mine Safety, Fleet Monitoring & Collision Prediction System

MineGuard AI is a low-cost, retrofit-oriented intelligent safety-assistance and centralized mine-monitoring platform designed for Low-Visibility and Fog conditions in open-cast mechanized mines (modeled after the NMDC Bailadila iron ore region).

This prototype includes simulated physical RGB front cameras, Thermal heat cameras, and FMCW Radar, fusing their returns to build operator awareness, predict Time-To-Collision (TTC), adjust recommended safety speeds, and reroute fleet vehicles around flooded roads.

---

## 🚀 System Architecture Flow

```text
📷 RGB Front Camera    🌡️ Thermal Heat Camera     📡 FMCW Radar Sensor
        │                    │                           │
        └────────────────────┼───────────────────────────┘
                             ▼
                    Multi-Sensor Fusion (Adaptive Weights)
                             │
                             ▼
                Visibility & Environment Engine
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
     Object Detection                 Road Health Mapping
 (Dumper, Person, Boulder)           (Pothole count, Water)
            │                                 │
            ▼                                 ▼
   Trajectory Projection             Adaptive Dynamic Speed Limits
  (Relative Velocity, TTC)           (Wet/slip thresholds)
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                    Unified Risk Engine
                             │
                             ▼
         Adaptive Safety States (Caution ↔ Critical)
                             │
                             ▼
       Central Command Decision Support (Rerouting, Stops)
```

---

## 🛠️ Key Engine Implementations

### 1. Visibility Calculation (`core/visibility_engine.py`)
Visibility (meters) drops exponentially in thick fog and wind-driven dust, and drops linearly under rain occlusion:
$$Visibility = \max\left(3.0,\ \min\left(150.0,\ \min(V_{fog},\ V_{rain},\ V_{dust})\right)\right)$$
*   **Fog decay**: $V_{fog} = 150 \times e^{-0.04 \times fog\%}$ (at 100% fog, visibility drops to 2.7 meters).
*   **Rain decay**: $V_{rain} = 150 \times (1.0 - 0.85 \times \frac{rain\%}{100})$.
*   **Dust decay**: $V_{dust} = 150 \times e^{-0.027 \times dust\%}$ (simulates blowing iron ore dust cloud blocks).

### 2. Multi-Sensor Fusion (`core/sensor_fusion.py`)
Sensors are re-weighted dynamically as environmental noise increases:
*   **RGB Camera**: Confidence drops severely in dense fog/dust ($1.0 - \max(fog \times 0.9, rain \times 0.7, dust \times 0.85)$).
*   **Thermal Camera**: Resilient to fog, but attenuated slightly by high water absorption and rain ($1.0 - (fog \times humidity \times 0.4) - (rain \times 0.25)$).
*   **Radar**: High weather resilience, minor backscatter drops in heavy rain ($1.0 - rain \times 0.1$).

Matched targets are clustered across multiple modalities using Euclidean distance groupings. If RGB, Thermal, and Radar agree on a close obstacle, the fused confidence climbs (Noisy-OR reinforcement) and class detection is locked.

### 3. Safety Speed Recommendation (`app.py`)
Dynamic Recommended Speed ($S_{rec}$) is calculated by evaluating compound safety limits:
*   **Road friction ceiling**: $40\text{ km/h} - (potholes \times 2.0) - (water\_accumulation \times 25.0)$
*   **Visibility ceiling**: $Vis < 5m \implies S_{rec} \le 12\text{ km/h}$
*   **Worker proximity ceiling**: $Distance \le 25m \implies S_{rec} \le 10\text{ km/h}$
*   **Perception self-awareness ceiling**: $Fusion\_Conf < 40\% \implies S_{rec} \le 15\text{ km/h}$; $Fusion\_Conf < 15\% \implies S_{rec} = 0.0$ (Controlled safety Stop warning).

### 4. Safest Route Engine (`core/route_engine.py`)
Calculates the safest route using Dijkstra's algorithm, where road weight is adjusted dynamically:
$$\text{Weight} = \text{Length (meters)} \times \left(1.0 + \frac{\text{Road Risk} + \text{Worker Proximity Penalty}}{15.0}\right)$$
Restricted roads (closed due to landslide risk or blast schedule) are assigned an infinite weight, forcing vehicles to take alternate routes (e.g. Workshop Bypass H-12 or East Rim Bypass H-13) even if they are physically longer.

---

## 📦 Project Structure

```text
D:\SIH\
├── app.py                      # Flask main server & API endpoints
├── requirements.txt            # Python dependencies
├── README.md                   # System documentation
├── data/                       # Static JSON files (nodes, roads, vehicles)
├── core/                       # Core analytical & threat engines
│   ├── weather_engine.py       # Atmospheric variables
│   ├── visibility_engine.py    # Visual range calculations
│   ├── sensor_fusion.py        # Multi-modal target grouping
│   ├── road_health.py          # Friction & road status coefficients
│   ├── collision_engine.py     # Trajectory TTC calculators
│   ├── risk_engine.py          # Unified safety state solver
│   ├── alert_engine.py         # Priority alert explanation compiler
│   └── route_engine.py         # Dijkstra safest route planner
├── simulation/                 # Active simulators updating state
│   ├── vehicle_simulator.py    # Moves fleet along roads
│   ├── worker_simulator.py     # Supervisor walk timelines
│   ├── weather_simulator.py    # Monsoon progression steps
│   ├── sensor_simulator.py     # Bounding box & noise generator
│   ├── road_simulator.py       # Pothole & flooding generator
│   └── scenario_engine.py      # Scripted scenario timeline manager
├── templates/
│   └── index.html              # Frontend UI container for 13 panels
└── static/
    ├── css/
    │   └── style.css           # Dark command center theme
    └── js/
        ├── app.js              # SPA navigation & REST api updates
        ├── map.js              # Concentric benches canvas map
        └── sensors.js          # RGB, Thermal & sweeps Radar drawing
```

---

## ⚡ Setup & Execution

### 1. Install Dependencies
Make sure Python 3.9+ is installed. Open a terminal in the project directory and run:
```bash
pip install -r requirements.txt
```

### 2. Run Flask Server
Run the Flask server script:
```bash
python app.py
```

### 3. Open Command Center Dashboard
Open your web browser and navigate to:
```text
http://localhost:5000
```

---

## 📌 Simulated Scenarios Guide

Open the **Scenario Simulator** tab on the left sidebar to execute any of the 8 predefined scenarios:
1.  **Scenario 1: Dense Fog Collision**: Visibility falls to 5m, RGB camera degrades, radar/thermal detect a dumper ahead, collision is predicted, and speed recommended actions avoid it.
2.  **Scenario 2: Heavy Rain & Potholes**: Downpour degrades road surface `H-07`. Laser road scanning calculates speed limits.
3.  **Scenario 3: Worker in Vehicle Path**: A worker walks into a dumper's path in thick fog. Thermal camera spots their body heat to trigger deceleration.
4.  **Scenario 4: Heavy Wind & Dust**: Iron ore dust reduces RGB camera opacity, testing sensor-fusion weights.
5.  **Scenario 5: Multiple Vehicle Conflict**: 3 dumpers meet at a ramp intersection, testing path-intersection safety.
6.  **Scenario 6: Sensor Failure**: V-01 thermal sensor fails, triggering self-aware confidence re-weighting and dispatch alerts.
7.  **Scenario 7: Bailadila Extreme Monsoon**: The main demonstration. Weather collapses, visibility drops to 3.5m, road degrades, vehicle V-01 speeds and encounters V-02, collision is predicted and avoided, worker walks in path and is spotted, heavy rain floods road `H-07`.
8.  **Scenario 8: Low Visibility & Damaged Road**: Forces vehicle `V-03` to automatically change its route via Dijkstra safest route planning, bypassing flooded road `H-07` in favor of bypass route `H-13`.

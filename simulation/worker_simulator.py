import math

class WorkerSimulator:
    @staticmethod
    def update_worker_position(worker, dt=0.5):
        """
        Updates worker positions along their preset path coordinates.
        Stationary workers remain in place.
        """
        if worker["status"] == "STATIONARY":
            return
            
        path = worker.get("path", [])
        path_idx = worker.get("path_index", 0)
        
        if not path or len(path) == 0:
            return
            
        target = path[path_idx]
        tx, ty = target["x"], target["y"]
        wx, wy = worker["position"]["x"], worker["position"]["y"]
        
        dx = tx - wx
        dy = ty - wy
        dist = math.sqrt(dx*dx + dy*dy)
        
        # If reached target point, cycle to next coordinate
        if dist < 2.0:
            worker["path_index"] = (path_idx + 1) % len(path)
            return
            
        # Move worker at their walking speed (mps)
        speed = worker.get("speed_mps", 0.8)
        step = speed * dt
        
        if step >= dist:
            worker["position"]["x"] = tx
            worker["position"]["y"] = ty
        else:
            ux = dx / dist
            uy = dy / dist
            worker["position"]["x"] = round(wx + ux * step, 1)
            worker["position"]["y"] = round(wy + uy * step, 1)

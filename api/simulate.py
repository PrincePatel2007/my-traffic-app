from flask import Flask, request, jsonify
import random

app = Flask(__name__)

class RealisticTrafficOptimizer:
    def __init__(self):
        self.lanes = ["North", "South", "East", "West"]
        self.ai_times = {"North": 45, "South": 45, "East": 60, "West": 60}
        self.fx_times = {"North": 45, "South": 45, "East": 60, "West": 60}
        self.ai_queues = {lane: 0 for lane in self.lanes}
        self.fx_queues = {lane: 0 for lane in self.lanes}
        self.max_shift_per_cycle = 10 
        self.recovery_jump = 25      
        self.emergency_cooldowns = {lane: 0 for lane in self.lanes}
        self.ai_total_loss = 0
        self.fx_total_loss = 0

    def generate_arrivals(self, lane, arrival_ranges):
        prob = random.random()
        arr_range = arrival_ranges[lane]
        spike_max = int(arr_range[1] * 1.5) + 1
        return random.randint(arr_range[1], spike_max) if prob < 0.10 else random.randint(arr_range[0], arr_range[1])

    def process_lane(self, lane, queue, max_green_time, red_time, avg_car_time):
        time_spent = 0
        cleared_cars = 0
        for _ in range(queue):
            car_time = random.randint(max(1, avg_car_time - 1), avg_car_time + 1)
            if time_spent + car_time <= max_green_time:
                cleared_cars += 1
                time_spent += car_time
            else:
                break 
        
        uncleared = queue - cleared_cars
        
        if uncleared == 0:
            time_left = max_green_time - time_spent
            if time_left > 3:
                actual_wasted = 3
                actual_green_used = time_spent + 3
            else:
                actual_wasted = time_left
                actual_green_used = max_green_time
        else:
            actual_wasted = 0
            actual_green_used = max_green_time
            
        # ==========================================
        # 🧠 QUEUING THEORY WAIT-TIME PENALTY
        # ==========================================
        # Time between 2 openings is the Red Time.
        # Average wait for cars arriving uniformly = Red Time / 2
        avg_wait_time = red_time / 2.0
        
        # Total wait penalty = Total number of vehicles waiting * Average wait time
        wait_penalty = queue * avg_wait_time
        
        # Total Loss = Wasted Green Time + (Uncleared cars suffering full Red Time) + Base Wait Penalty
        loss = actual_wasted + (uncleared * red_time) + wait_penalty
        
        return uncleared, actual_wasted, loss, actual_green_used, avg_wait_time, wait_penalty

    def ask_gemini_for_targets(self, stats, avg_car_time):
        targets = {}
        for l in self.lanes:
            current = self.ai_times[l]
            # Heuristic: aggressively punish uncleared cars to prevent cascading jams, 
            # lightly pull back on wasted time to shrink total cycle length (which lowers red-time penalties!)
            adjust = (stats[l]["failed"] * avg_car_time * 2.0) - (stats[l]["wasted_allocation"] * 0.25)
            targets[l] = max(15, min(160, int(current + adjust)))
        return targets

@app.route('/api/simulate', methods=['POST', 'GET'])
def simulate():
    if request.method == 'GET':
        return jsonify({"status": "SUCCESS! Python Backend is Live!"})

    data = request.json
    total_cycles = data.get('total_cycles', 50)
    avg_car_time = data.get('avg_car_time', 5)
    arrival_ranges = data.get('arrival_ranges', {"North": [2, 12], "South": [2, 12], "East": [5, 15], "West": [5, 15]})
    ev_probs = data.get('ev_probs', {"North": 0.05, "South": 0.05, "East": 0.05, "West": 0.05})

    sim = RealisticTrafficOptimizer()
    log_data_ai = []
    log_data_fx = []

    manual_ns, manual_ew = 45, 60

    for cycle in range(1, total_cycles + 1):
        cycle_stats_ai = {}
        
        sim.fx_times["North"] = manual_ns
        sim.fx_times["South"] = manual_ns
        sim.fx_times["East"] = manual_ew
        sim.fx_times["West"] = manual_ew
        
        if cycle == 1:
            for lane in sim.lanes:
                sim.fx_times[lane] = manual_ns if lane in ["North", "South"] else manual_ew
                expected_vehicles = sum(arrival_ranges[lane]) / 2.0
                smart_starting_time = int((expected_vehicles * avg_car_time) + 5)
                sim.ai_times[lane] = max(15, min(160, smart_starting_time))

        total_ai_cycle_time = sum(sim.ai_times.values())
        total_fx_cycle_time = sum(sim.fx_times.values())

        new_arrivals = {}
        for lane in sim.lanes:
            new_cars = sim.generate_arrivals(lane, arrival_ranges)
            new_arrivals[lane] = new_cars
            sim.ai_queues[lane] += new_cars
            sim.fx_queues[lane] += new_cars

        ev_priorities = {"Ambulance": 1, "Fire": 2, "Police": 3}
        ev_icons = {"Ambulance": "🚑", "Fire": "🚒", "Police": "🚓"}
        active_evs = []
        
        for lane in sim.lanes:
            if random.random() < ev_probs[lane]: 
                ev_type = random.choice(list(ev_priorities.keys()))
                pos_ai = random.randint(1, max(1, sim.ai_queues[lane]))
                pos_fx = random.randint(1, max(1, sim.fx_queues[lane]))
                active_evs.append({"lane": lane, "type": ev_type, "icon": ev_icons[ev_type], "priority": ev_priorities[ev_type], "pos_ai": pos_ai, "pos_fx": pos_fx})
                sim.emergency_cooldowns[lane] = 3 
                
        active_evs.sort(key=lambda x: (x["priority"], x["pos_ai"]))

        ai_execution_order = [ev["lane"] for ev in active_evs]
        for lane in sim.lanes:
            if lane not in ai_execution_order: ai_execution_order.append(lane)
                
        fx_execution_order = ["North", "South", "East", "West"]

        # PROCESS AI SYSTEM
        for phase_step, lane in enumerate(ai_execution_order, 1):
            q_before_ai = sim.ai_queues[lane]
            base_ai_time = sim.ai_times[lane]
            max_ai_time = base_ai_time
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            
            event_ai = ""
            if ev_data:
                safe_car_time = avg_car_time + 1 
                max_ai_time = max(max_ai_time, ev_data["pos_ai"] * safe_car_time)
                event_ai = f"{ev_data['icon']} EVP ✅ | "
            elif sim.emergency_cooldowns[lane] > 0:
                event_ai = "⚡ Recovery | "

            ai_red_time = total_ai_cycle_time - max_ai_time
            ai_fail, ai_waste, ai_l, ai_used_time, ai_avg_wait, ai_wait_pen = sim.process_lane(lane, q_before_ai, max_ai_time, ai_red_time, avg_car_time)
            
            sim.ai_queues[lane] = ai_fail
            sim.ai_total_loss += ai_l
            cycle_stats_ai[lane] = {"failed": ai_fail, "wasted_allocation": max_ai_time - ai_used_time}

            timing_str_ai = f"{max_ai_time}s ✂️ Cut to {ai_used_time}s" if ai_used_time < max_ai_time else f"{max_ai_time}s"
            if max_ai_time != base_ai_time: timing_str_ai = f"🚨 {timing_str_ai}"
            queue_display_ai = f"🛑 {q_before_ai} 🚗💥" if q_before_ai > 50 else str(q_before_ai)

            # Display the wait penalty clearly to the judges
            event_ai += f"Avg Wait: {int(ai_avg_wait)}s (Pen: {int(ai_wait_pen)})"

            log_data_ai.append({"Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": timing_str_ai, "Queue": queue_display_ai, "Cycle Loss": int(ai_l), "Events": event_ai})

        # PROCESS FIXED SYSTEM
        for phase_step, lane in enumerate(fx_execution_order, 1):
            q_before_fx = sim.fx_queues[lane]
            max_fx_time = sim.fx_times[lane]
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            
            event_fx = ""
            if ev_data:
                req_time_fx = ev_data["pos_fx"] * (avg_car_time + 1)
                event_fx = f"{ev_data['icon']} " + ("⚠️ Lucky Cleared | " if max_fx_time >= req_time_fx else "❌ STRANDED! | ")

            fx_red_time = total_fx_cycle_time - max_fx_time
            fx_fail, fx_waste, fx_l, fx_used_time, fx_avg_wait, fx_wait_pen = sim.process_lane(lane, q_before_fx, max_fx_time, fx_red_time, avg_car_time)
            
            sim.fx_queues[lane] = fx_fail
            sim.fx_total_loss += fx_l

            timing_str_fx = f"{max_fx_time}s ✂️ Cut to {fx_used_time}s" if fx_used_time < max_fx_time else f"{max_fx_time}s"
            queue_display_fx = f"🛑 {q_before_fx} 🚗💥" if q_before_fx > 50 else str(q_before_fx)

            # Display the wait penalty clearly to the judges
            event_fx += f"Avg Wait: {int(fx_avg_wait)}s (Pen: {int(fx_wait_pen)})"

            log_data_fx.append({"Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": timing_str_fx, "Queue": queue_display_fx, "Cycle Loss": int(fx_l), "Events": event_fx})

        # Update AI Timings
        target_times = sim.ask_gemini_for_targets(cycle_stats_ai, avg_car_time)
        is_any_recovering = any(c > 0 for c in sim.emergency_cooldowns.values())
        for lane in sim.lanes:
            difference = max(15, min(160, target_times.get(lane, sim.ai_times[lane]))) - sim.ai_times[lane]
            shift = max(-sim.recovery_jump, min(sim.max_shift_per_cycle, difference)) if (is_any_recovering and sim.emergency_cooldowns[lane] > 0) else max(-sim.max_shift_per_cycle, min(sim.max_shift_per_cycle if not is_any_recovering else sim.recovery_jump, difference))
            sim.ai_times[lane] += shift
            if sim.emergency_cooldowns[lane] > 0: sim.emergency_cooldowns[lane] -= 1

    return jsonify({"ai_logs": log_data_ai, "fx_logs": log_data_fx})
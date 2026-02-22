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

    def simulate_lane_traffic(self, queue, allocated_time, avg_car_time, can_cut_early):
        time_spent = 0
        cleared_cars = 0
        for _ in range(queue):
            car_time = random.randint(max(1, avg_car_time - 1), avg_car_time + 1)
            if time_spent + car_time <= allocated_time:
                cleared_cars += 1
                time_spent += car_time
            else:
                break 
        
        uncleared = queue - cleared_cars
        
        # AI cuts the light early. Fixed timer blindly waits the full allocated time.
        if can_cut_early:
            if uncleared == 0:
                used_time = min(allocated_time, time_spent + 3) # 3s clearance time
                wasted = used_time - time_spent
            else:
                used_time = allocated_time
                wasted = 0
        else:
            used_time = allocated_time
            wasted = allocated_time - time_spent if uncleared == 0 else 0
                
        return uncleared, used_time, wasted

    def ask_gemini_for_targets(self, stats, avg_car_time):
        targets = {}
        for l in self.lanes:
            current = self.ai_times[l]
            # Heuristic keeps AI times balanced based on failed cars and wasted time
            adjust = (stats[l]["failed"] * avg_car_time * 2.0) - (stats[l]["wasted"] * 0.25)
            targets[l] = max(15, min(160, int(current + adjust)))
        return targets

@app.route('/api/simulate', methods=['POST', 'GET'])
def simulate():
    if request.method == 'GET':
        return jsonify({"status": "SUCCESS! Python is alive with Advanced Queuing Penalties!"})

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
                expected_vehicles = sum(arrival_ranges[lane]) / 2.0
                smart_starting_time = int((expected_vehicles * avg_car_time) + 5)
                sim.ai_times[lane] = max(15, min(160, smart_starting_time))

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

        # 🧠 PHASE 1: PRE-CALCULATE ACTUAL TIMES USED
        ai_phase_results = {}
        total_ai_used_time = 0
        for lane in ai_execution_order:
            q = sim.ai_queues[lane]
            alloc = sim.ai_times[lane]
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            if ev_data: alloc = max(alloc, ev_data["pos_ai"] * (avg_car_time + 1))
            
            unc, used, wst = sim.simulate_lane_traffic(q, alloc, avg_car_time, can_cut_early=True)
            ai_phase_results[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': used, 'wst': wst, 'ev': ev_data}
            total_ai_used_time += used

        fx_phase_results = {}
        total_fx_used_time = sum(sim.fx_times.values())
        for lane in fx_execution_order:
            q = sim.fx_queues[lane]
            alloc = sim.fx_times[lane]
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            
            unc, used, wst = sim.simulate_lane_traffic(q, alloc, avg_car_time, can_cut_early=False)
            fx_phase_results[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': alloc, 'wst': wst, 'ev': ev_data}

        # 🧠 PHASE 2: APPLY WEIGHTED RED-TIME PENALTIES (The Magic Math)
        
        # --- PROCESS AI LOGS ---
        for phase_step, lane in enumerate(ai_execution_order, 1):
            res = ai_phase_results[lane]
            red_time = total_ai_used_time - res['used']
            
            # SPLIT WAIT PENALTY: Holdovers waited FULL red time. New arrivals waited HALF.
            holdovers = max(0, res['q'] - new_arrivals[lane])
            new_cars = new_arrivals[lane]
            wait_penalty = (holdovers * red_time) + (new_cars * (red_time / 2.0))
            
            # WEIGHTED PENALTIES
            weighted_wasted = res['wst'] * 5              # Wasted time is punished 5x
            uncleared_penalty = res['unc'] * (red_time * 1.5) # Uncleared cars punished 1.5x Red Time

            loss = weighted_wasted + uncleared_penalty + wait_penalty
            sim.ai_total_loss += loss
            sim.ai_queues[lane] = res['unc']
            cycle_stats_ai[lane] = {"failed": res['unc'], "wasted": res['wst']}

            event_ai = ""
            if res['ev']: event_ai = f"{res['ev']['icon']} EVP ✅ | "
            elif sim.emergency_cooldowns[lane] > 0: event_ai = "⚡ Recovery | "
            event_ai += f"Wait Pen: {int(wait_penalty)} pts"

            timing_str = f"{res['alloc']}s ✂️ Cut to {res['used']}s" if res['used'] < res['alloc'] else f"{res['alloc']}s"
            if res['alloc'] != sim.ai_times[lane]: timing_str = f"🚨 {timing_str}"

            log_data_ai.append({
                "Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": timing_str, 
                "Queue": f"🛑 {res['q']} 🚗💥" if res['q'] > 50 else str(res['q']), "Cycle Loss": int(loss), "Events": event_ai,
                "Arrivals": new_arrivals[lane], "Failed": res['unc'], "Wasted": res['wst'], "WaitPenalty": int(wait_penalty)
            })

        # --- PROCESS FIXED LOGS ---
        for phase_step, lane in enumerate(fx_execution_order, 1):
            res = fx_phase_results[lane]
            red_time = total_fx_used_time - res['used']
            
            # SPLIT WAIT PENALTY: Holdovers waited FULL red time. New arrivals waited HALF.
            holdovers = max(0, res['q'] - new_arrivals[lane])
            new_cars = new_arrivals[lane]
            wait_penalty = (holdovers * red_time) + (new_cars * (red_time / 2.0))
            
            # WEIGHTED PENALTIES
            weighted_wasted = res['wst'] * 5              # Wasted time is punished 5x
            uncleared_penalty = res['unc'] * (red_time * 1.5) # Uncleared cars punished 1.5x Red Time
            
            loss = weighted_wasted + uncleared_penalty + wait_penalty
            sim.fx_total_loss += loss
            sim.fx_queues[lane] = res['unc']

            event_fx = ""
            if res['ev']:
                req = res['ev']['pos_fx'] * (avg_car_time + 1)
                event_fx = f"{res['ev']['icon']} " + ("⚠️ Lucky Cleared | " if res['alloc'] >= req else "❌ STRANDED! | ")
            event_fx += f"Wait Pen: {int(wait_penalty)} pts"

            log_data_fx.append({
                "Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": f"{res['alloc']}s", 
                "Queue": f"🛑 {res['q']} 🚗💥" if res['q'] > 50 else str(res['q']), "Cycle Loss": int(loss), "Events": event_fx,
                "Arrivals": new_arrivals[lane], "Failed": res['unc'], "Wasted": res['wst'], "WaitPenalty": int(wait_penalty)
            })

        # Update AI Timings
        target_times = sim.ask_gemini_for_targets(cycle_stats_ai, avg_car_time)
        is_any_recovering = any(c > 0 for c in sim.emergency_cooldowns.values())
        for lane in sim.lanes:
            diff = max(15, min(160, target_times.get(lane, sim.ai_times[lane]))) - sim.ai_times[lane]
            shift = max(-sim.recovery_jump, min(sim.max_shift_per_cycle, diff)) if (is_any_recovering and sim.emergency_cooldowns[lane] > 0) else max(-sim.max_shift_per_cycle, min(sim.max_shift_per_cycle, diff))
            sim.ai_times[lane] += shift
            if sim.emergency_cooldowns[lane] > 0: sim.emergency_cooldowns[lane] -= 1

    return jsonify({"ai_logs": log_data_ai, "fx_logs": log_data_fx})
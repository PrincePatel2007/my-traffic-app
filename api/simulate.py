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
        self.max_shift_per_cycle = 15 
        self.recovery_jump = 25      
        self.emergency_cooldowns = {lane: 0 for lane in self.lanes}
        self.ai_total_loss = 0
        self.fx_total_loss = 0

    def generate_arrivals(self, lane, arrival_ranges_per_min, cycle_length_mins):
        # NEW: Converts per-minute arrival rates into exact cycle batches
        prob = random.random()
        min_arr = int(arrival_ranges_per_min[lane][0] * cycle_length_mins)
        max_arr = int(arrival_ranges_per_min[lane][1] * cycle_length_mins)
        
        spike_max = int(max_arr * 1.5) + 1
        return random.randint(max_arr, spike_max) if prob < 0.10 else random.randint(min_arr, max_arr)

    def simulate_lane_traffic(self, queue, allocated_time, avg_car_time, can_cut_early, lane_count):
        time_spent = 0
        cleared_cars = 0
        
        # NEW: Multi-lane clearance logic
        while cleared_cars < queue:
            # The time it takes for the front row of cars to clear
            car_time = random.randint(max(1, avg_car_time - 1), avg_car_time + 1)
            
            if time_spent + car_time <= allocated_time:
                # If there are 3 lanes, 3 cars clear the intersection simultaneously
                cleared_cars += min(lane_count, queue - cleared_cars)
                time_spent += car_time
            else:
                break 
        
        uncleared = queue - cleared_cars
        
        # NEW: Continuous Flow Logic (Removed 3s gap-out)
        if can_cut_early:
            # AI instantly cuts the light the millisecond the queue hits 0
            used_time = time_spent if uncleared == 0 else allocated_time
            wasted = used_time - time_spent if uncleared == 0 else 0
        else:
            used_time = allocated_time
            wasted = allocated_time - time_spent if uncleared == 0 else 0
                
        return uncleared, used_time, wasted

    def calculate_density_targets(self, queues, stats, avg_car_time, lanes_config):
        # NEW: True Density Queue Balancing
        targets = {}
        for l in self.lanes:
            lane_count = lanes_config["NS"] if l in ["North", "South"] else lanes_config["EW"]
            
            # Step 1: Exactly how much time does this queue need to clear across all its lanes?
            ideal_time = (queues[l] / lane_count) * avg_car_time
            
            # Step 2: Add failure recovery to prevent starvation
            recovery_buffer = stats.get(l, {}).get("failed", 0) * avg_car_time
            
            # Step 3: Add 10% continuous-flow buffer for cars that will arrive DURING the green light
            final_target = (ideal_time + recovery_buffer) * 1.10
            
            targets[l] = max(15, min(160, int(final_target)))
        return targets

@app.route('/api/simulate', methods=['POST', 'GET'])
def simulate():
    if request.method == 'GET':
        return jsonify({"status": "SUCCESS! Python is alive with Queue Density Balancing!"})

    data = request.json
    total_cycles = data.get('total_cycles', 50)
    avg_car_time = data.get('avg_car_time', 5)
    
    # NEW VARIABLES
    arrivals_per_min = data.get('arrivals_per_min', {"North": [10, 25], "South": [10, 25], "East": [15, 35], "West": [15, 35]})
    lanes_config = data.get('lanes', {"NS": 3, "EW": 3})
    
    ev_probs = data.get('ev_probs', {"North": 0.05, "South": 0.05, "East": 0.05, "West": 0.05})
    user_fx_times = data.get('fx_times', {"North": 45, "South": 45, "East": 60, "West": 60})

    sim = RealisticTrafficOptimizer()
    log_data_ai = []
    log_data_fx = []

    for cycle in range(1, total_cycles + 1):
        cycle_stats_ai = {}
        sim.fx_times = user_fx_times.copy()
        
        baseline_cycle_mins = sum(sim.fx_times.values()) / 60.0

        if cycle == 1:
            for lane in sim.lanes:
                expected_per_min = sum(arrivals_per_min[lane]) / 2.0
                expected_per_cycle = expected_per_min * baseline_cycle_mins
                lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
                smart_starting_time = int((expected_per_cycle / lane_count) * avg_car_time)
                sim.ai_times[lane] = max(15, min(160, smart_starting_time))

        new_arrivals = {}
        for lane in sim.lanes:
            new_cars = sim.generate_arrivals(lane, arrivals_per_min, baseline_cycle_mins)
            new_arrivals[lane] = new_cars
            sim.ai_queues[lane] += new_cars
            sim.fx_queues[lane] += new_cars

        ev_priorities = {"Ambulance": 1, "Fire Truck": 2, "Police Car": 3}
        ev_icons = {"Ambulance": "🚑", "Fire Truck": "🚒", "Police Car": "🚓"}
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

        # 🧠 PHASE 1: ACTUAL TIMES USED WITH LANES
        ai_phase_results = {}
        total_ai_used_time = 0
        for lane in ai_execution_order:
            q = sim.ai_queues[lane]
            alloc = sim.ai_times[lane]
            lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
            
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            if ev_data: 
                # EV position divided by lanes (if ambulance is 9th in a 3-lane road, it's effectively 3rd in line)
                effective_pos = max(1, ev_data["pos_ai"] // lane_count)
                alloc = max(alloc, effective_pos * (avg_car_time + 1))
            
            unc, used, wst = sim.simulate_lane_traffic(q, alloc, avg_car_time, True, lane_count)
            ai_phase_results[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': used, 'wst': wst, 'ev': ev_data}
            total_ai_used_time += used

        fx_phase_results = {}
        total_fx_used_time = sum(sim.fx_times.values())
        for lane in fx_execution_order:
            q = sim.fx_queues[lane]
            alloc = sim.fx_times[lane]
            lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            
            unc, used, wst = sim.simulate_lane_traffic(q, alloc, avg_car_time, False, lane_count)
            fx_phase_results[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': alloc, 'wst': wst, 'ev': ev_data}

        # 🧠 PHASE 2: CALCULATE WEIGHTED PENALTIES
        for phase_step, lane in enumerate(ai_execution_order, 1):
            res = ai_phase_results[lane]
            red_time = total_ai_used_time - res['used']
            avg_wait = red_time / 2.0
            
            holdovers = max(0, res['q'] - new_arrivals[lane])
            new_cars = new_arrivals[lane]
            wait_penalty = (holdovers * red_time) + (new_cars * avg_wait)
            
            weighted_wasted = res['wst'] * 5              
            uncleared_penalty = res['unc'] * (red_time * 1.5) 

            loss = weighted_wasted + uncleared_penalty + wait_penalty
            sim.ai_total_loss += loss
            sim.ai_queues[lane] = res['unc']
            cycle_stats_ai[lane] = {"failed": res['unc'], "wasted": res['wst']}

            event_ai = ""
            if res['ev']: event_ai = f"{res['ev']['icon']} {res['ev']['type']} (Pos {res['ev']['pos_ai']}) Cleared ✅ | "
            elif sim.emergency_cooldowns[lane] > 0: event_ai = "⚡ Recovery | "

            timing_str = f"{res['alloc']}s ✂️ Cut to {res['used']}s" if res['used'] < res['alloc'] else f"{res['alloc']}s"
            if res['alloc'] != sim.ai_times[lane]: timing_str = f"🚨 {timing_str}"

            log_data_ai.append({
                "Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": timing_str, 
                "Queue": f"🛑 {res['q']} 🚗💥" if res['q'] > 50 else str(res['q']), "Cycle Loss": int(loss), "Events": event_ai,
                "Arrivals": new_arrivals[lane], "Failed": res['unc'], "Wasted": res['wst'], 
                "AvgWait": int(avg_wait), "WaitPenalty": int(wait_penalty)
            })

        for phase_step, lane in enumerate(fx_execution_order, 1):
            res = fx_phase_results[lane]
            red_time = total_fx_used_time - res['used']
            avg_wait = red_time / 2.0
            
            holdovers = max(0, res['q'] - new_arrivals[lane])
            new_cars = new_arrivals[lane]
            wait_penalty = (holdovers * red_time) + (new_cars * avg_wait)
            
            weighted_wasted = res['wst'] * 5              
            uncleared_penalty = res['unc'] * (red_time * 1.5) 
            
            loss = weighted_wasted + uncleared_penalty + wait_penalty
            sim.fx_total_loss += loss
            sim.fx_queues[lane] = res['unc']

            event_fx = ""
            if res['ev']:
                lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
                effective_pos = max(1, res['ev']['pos_fx'] // lane_count)
                req = effective_pos * (avg_car_time + 1)
                event_fx = f"{res['ev']['icon']} {res['ev']['type']} (Pos {res['ev']['pos_fx']}) " + ("⚠️ Lucky Cleared | " if res['alloc'] >= req else "❌ STRANDED! | ")

            log_data_fx.append({
                "Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": f"{res['alloc']}s", 
                "Queue": f"🛑 {res['q']} 🚗💥" if res['q'] > 50 else str(res['q']), "Cycle Loss": int(loss), "Events": event_fx,
                "Arrivals": new_arrivals[lane], "Failed": res['unc'], "Wasted": res['wst'], 
                "AvgWait": int(avg_wait), "WaitPenalty": int(wait_penalty)
            })

        # UPDATE AI TARGETS USING NEW DENSITY MATH
        target_times = sim.calculate_density_targets(sim.ai_queues, cycle_stats_ai, avg_car_time, lanes_config)
        is_any_recovering = any(c > 0 for c in sim.emergency_cooldowns.values())
        for lane in sim.lanes:
            diff = max(15, min(160, target_times.get(lane, sim.ai_times[lane]))) - sim.ai_times[lane]
            shift = max(-sim.recovery_jump, min(sim.max_shift_per_cycle, diff)) if (is_any_recovering and sim.emergency_cooldowns[lane] > 0) else max(-sim.max_shift_per_cycle, min(sim.max_shift_per_cycle, diff))
            sim.ai_times[lane] += shift
            if sim.emergency_cooldowns[lane] > 0: sim.emergency_cooldowns[lane] -= 1

    return jsonify({"ai_logs": log_data_ai, "fx_logs": log_data_fx})
from flask import Flask, request, jsonify
import random

app = Flask(__name__)

class ReinforcementLearningAgent:
    def __init__(self, lanes):
        self.lanes = lanes
        self.weights = {lane: {"density_importance": 1.0, "cross_traffic_pressure": 0.1} for lane in lanes}
        
        # FIX: Dramatically lowered learning rate for smooth, stable convergence
        self.learning_rate = 0.005 

    def get_target_time(self, lane, queue, lane_count, cross_queues_total, avg_car_time):
        w_density = self.weights[lane]["density_importance"]
        w_cross = self.weights[lane]["cross_traffic_pressure"]

        ideal_time = (queue / lane_count) * avg_car_time * w_density
        cross_pressure_reduction = cross_queues_total * w_cross
        
        target = ideal_time - cross_pressure_reduction
        return max(15, min(160, int(target)))

    def update_weights(self, lane, wasted, failed):
        if wasted > 0:
            self.weights[lane]["density_importance"] -= self.learning_rate * 0.5
            self.weights[lane]["cross_traffic_pressure"] += self.learning_rate * 0.2
        if failed > 0:
            self.weights[lane]["density_importance"] += self.learning_rate * 1.0
            self.weights[lane]["cross_traffic_pressure"] -= self.learning_rate * 0.1

        # FIX: Tightened the safety bounds so the RL model can't explore into disastrous extremes
        self.weights[lane]["density_importance"] = max(0.8, min(2.0, self.weights[lane]["density_importance"]))
        self.weights[lane]["cross_traffic_pressure"] = max(0.05, min(0.4, self.weights[lane]["cross_traffic_pressure"]))


class RealisticTrafficOptimizer:
    def __init__(self):
        self.lanes = ["North", "South", "East", "West"]
        self.ai_times = {"North": 45, "South": 45, "East": 60, "West": 60}
        self.fx_times = {"North": 45, "South": 45, "East": 60, "West": 60}
        self.ai_queues = {lane: 0 for lane in self.lanes}
        self.fx_queues = {lane: 0 for lane in self.lanes}
        self.emergency_cooldowns = {lane: 0 for lane in self.lanes}
        self.ai_total_loss = 0
        self.fx_total_loss = 0
        self.rl_agent = ReinforcementLearningAgent(self.lanes)

    def generate_arrivals(self, lane, arrival_ranges_per_min, cycle_length_mins):
        prob = random.random()
        min_arr = int(arrival_ranges_per_min[lane][0] * cycle_length_mins)
        max_arr = int(arrival_ranges_per_min[lane][1] * cycle_length_mins)
        spike_max = int(max_arr * 1.5) + 1
        return random.randint(max_arr, spike_max) if prob < 0.10 else random.randint(min_arr, max_arr)

    def simulate_lane_traffic(self, queue, allocated_time, avg_car_time, can_cut_early, lane_count):
        time_spent = 0
        cleared_cars = 0
        
        while cleared_cars < queue:
            car_time = random.randint(max(1, avg_car_time - 1), avg_car_time + 1)
            if time_spent + car_time <= allocated_time:
                cleared_cars += min(lane_count, queue - cleared_cars)
                time_spent += car_time
            else:
                break 
        
        uncleared = queue - cleared_cars
        
        if can_cut_early:
            used_time = time_spent if uncleared == 0 else allocated_time
            wasted = used_time - time_spent if uncleared == 0 else 0
        else:
            used_time = allocated_time
            wasted = allocated_time - time_spent if uncleared == 0 else 0
                
        return uncleared, used_time, wasted

@app.route('/api/simulate', methods=['POST', 'GET'])
def simulate():
    if request.method == 'GET':
        return jsonify({"status": "SUCCESS! Stabilized RL Agent is Live!"})

    data = request.json
    total_cycles = data.get('total_cycles', 50)
    avg_car_time = data.get('avg_car_time', 5)
    arrivals_per_min = data.get('arrivals_per_min', {"North": [10, 25], "South": [10, 25], "East": [15, 35], "West": [15, 35]})
    lanes_config = data.get('lanes', {"NS": 3, "EW": 3})
    ev_probs = data.get('ev_probs', {"North": 0.05, "South": 0.05, "East": 0.05, "West": 0.05})
    user_fx_times = data.get('fx_times', {"North": 45, "South": 45, "East": 60, "West": 60})

    sim = RealisticTrafficOptimizer()
    log_data_ai = []
    log_data_fx = []

    for cycle in range(1, total_cycles + 1):
        sim.fx_times = user_fx_times.copy()
        baseline_cycle_mins = sum(sim.fx_times.values()) / 60.0

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

        # 🧠 PHASE 1: SIMULATE AI LANES
        ai_phase_results = {}
        total_ai_used_time = 0
        for lane in ai_execution_order:
            q = sim.ai_queues[lane]
            alloc = sim.ai_times[lane]
            lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
            
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            if ev_data: 
                effective_pos = max(1, ev_data["pos_ai"] // lane_count)
                alloc = max(alloc, effective_pos * (avg_car_time + 1))
            
            unc, used, wst = sim.simulate_lane_traffic(q, alloc, avg_car_time, True, lane_count)
            ai_phase_results[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': used, 'wst': wst, 'ev': ev_data}
            total_ai_used_time += used

        # 🧠 PHASE 1: SIMULATE FIXED LANES
        fx_phase_results = {}
        total_fx_used_time = sum(sim.fx_times.values())
        for lane in fx_execution_order:
            q = sim.fx_queues[lane]
            alloc = sim.fx_times[lane]
            lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            
            unc, used, wst = sim.simulate_lane_traffic(q, alloc, avg_car_time, False, lane_count)
            fx_phase_results[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': alloc, 'wst': wst, 'ev': ev_data}

        # 🧠 PHASE 2: APPLY RL MULTIPLIERS & CALCULATE LOSS
        def calculate_rl_loss(lane, res, red_time, is_ai):
            lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
            holdovers = max(0, res['q'] - new_arrivals[lane])
            avg_wait = red_time / 2.0
            wait_penalty = (holdovers * red_time) + (new_arrivals[lane] * avg_wait)
            
            # --- DYNAMIC RL MULTIPLIERS ---
            flags = []
            
            stuck_mult = 2.5 if holdovers > 0 else 1.0
            if holdovers > 0: flags.append("🔄 Multi-Cycle Jam")
            
            timeout_mult = 1.5 if red_time > 60 else 1.0
            if red_time > 60: flags.append("⏳ >60s Wait Timeout")
            
            jam_mult = 3.0 if res['q'] > (30 * lane_count) else 1.0
            if jam_mult > 1.0: flags.append("💥 Critical Density")

            loss = (res['wst'] * 5) + (res['unc'] * (red_time * stuck_mult * timeout_mult)) + (wait_penalty * jam_mult)
            
            if is_ai:
                sim.rl_agent.update_weights(lane, res['wst'], res['unc'])
                
            return int(loss), int(avg_wait), int(wait_penalty), flags

        # PROCESS AI LOGS
        for phase_step, lane in enumerate(ai_execution_order, 1):
            res = ai_phase_results[lane]
            red_time = total_ai_used_time - res['used']
            loss, avg_wait, wait_penalty, flags = calculate_rl_loss(lane, res, red_time, True)
            
            sim.ai_total_loss += loss
            sim.ai_queues[lane] = res['unc']

            event_ai = f"{res['ev']['icon']} {res['ev']['type']} (Pos {res['ev']['pos_ai']}) ✅ | " if res['ev'] else ("⚡ Recovery | " if sim.emergency_cooldowns[lane] > 0 else "")
            timing_str = f"{res['alloc']}s ✂️ Cut to {res['used']}s" if res['used'] < res['alloc'] else f"{res['alloc']}s"

            log_data_ai.append({
                "Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": timing_str, 
                "Queue": str(res['q']), "Cycle Loss": loss, "Events": event_ai,
                "Arrivals": new_arrivals[lane], "Failed": res['unc'], "Wasted": res['wst'], "AvgWait": avg_wait, "WaitPenalty": wait_penalty, "Flags": flags
            })

        # PROCESS FIXED LOGS
        for phase_step, lane in enumerate(fx_execution_order, 1):
            res = fx_phase_results[lane]
            red_time = total_fx_used_time - res['used']
            loss, avg_wait, wait_penalty, flags = calculate_rl_loss(lane, res, red_time, False)
            
            sim.fx_total_loss += loss
            sim.fx_queues[lane] = res['unc']

            event_fx = ""
            if res['ev']:
                lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
                req = max(1, res['ev']['pos_fx'] // lane_count) * (avg_car_time + 1)
                event_fx = f"{res['ev']['icon']} {res['ev']['type']} (Pos {res['ev']['pos_fx']}) " + ("⚠️ Lucky | " if res['alloc'] >= req else "❌ STRANDED! | ")

            log_data_fx.append({
                "Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": f"{res['alloc']}s", 
                "Queue": str(res['q']), "Cycle Loss": loss, "Events": event_fx,
                "Arrivals": new_arrivals[lane], "Failed": res['unc'], "Wasted": res['wst'], "AvgWait": avg_wait, "WaitPenalty": wait_penalty, "Flags": flags
            })

        # ==========================================
        # AI ACTION DECISION (Based on learned weights)
        # ==========================================
        cross_traffic_sums = {lane: sum(sim.ai_queues[l] for l in sim.lanes if l != lane) for lane in sim.lanes}
        
        for lane in sim.lanes:
            lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
            
            target_time = sim.rl_agent.get_target_time(lane, sim.ai_queues[lane], lane_count, cross_traffic_sums[lane], avg_car_time)
            
            if sim.emergency_cooldowns[lane] > 0:
                target_time += 15
                sim.emergency_cooldowns[lane] -= 1
                
            sim.ai_times[lane] = target_time

    return jsonify({"ai_logs": log_data_ai, "fx_logs": log_data_fx})
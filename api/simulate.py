from flask import Flask, request, jsonify
import random
import traceback

app = Flask(__name__)

class GradientRLAgent:
    def __init__(self, lanes):
        self.lanes = lanes
        self.weights = {lane: 1.0 for lane in lanes}
        self.learning_rate = 0.01 

    def get_action(self, lane, queue, lane_count, avg_car_time):
        if queue == 0:
            return 0 
            
        safe_lane_count = max(1, lane_count)
        cars_per_lane = queue / safe_lane_count
        
        # =======================================================
        # ARTERIAL FLUSHING: 
        # If a lane exceeds 10 cars per lane, it is in a Gridlock State.
        # We give it a 1.5x time multiplier to flush the massive wave. 
        # This will naturally force the AI to sacrifice the cross-streets (dropping them to 3s).
        # =======================================================
        if cars_per_lane > 10.0:
            ideal_base_time = cars_per_lane * avg_car_time * 1.5
        else:
            ideal_base_time = cars_per_lane * avg_car_time
            
        target = ideal_base_time * self.weights[lane]
        
        # Allow micro-phases for calculated sacrifices (enough time for 1 car)
        min_green = max(3, int(avg_car_time)) 
        return max(min_green, int(round(target)))

    def backpropagate(self, lane, failed_cars, wasted_time, holdovers):
        if holdovers > 0:
            self.weights[lane] += self.learning_rate * min(30, holdovers) * 1.0
        elif failed_cars > 0:
            self.weights[lane] += self.learning_rate * min(20, failed_cars) * 0.4
        elif wasted_time > 0:
            self.weights[lane] -= self.learning_rate * (wasted_time / 5.0)
        else:
            self.weights[lane] -= self.learning_rate * 0.1

        self.weights[lane] = max(0.1, min(5.0, self.weights[lane]))


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
        self.ml_agent = GradientRLAgent(self.lanes)
        self.last_ai_cycle_time = 120 
        self.last_fx_cycle_time = 120

    def generate_arrivals(self, lane, arrival_ranges_per_min, cycle_length_mins):
        prob = random.random()
        min_arr = int(arrival_ranges_per_min[lane][0] * cycle_length_mins)
        max_arr = int(arrival_ranges_per_min[lane][1] * cycle_length_mins)
        safe_max = max(min_arr, max_arr)
        spike_max = int(safe_max * 1.5) + 1
        return random.randint(safe_max, spike_max) if prob < 0.10 else random.randint(min_arr, safe_max)

    def simulate_lane_traffic(self, lane, queue, allocated_green, avg_car_time, can_cut_early, lane_count):
        if allocated_green == 0:
            return queue, 0, 0, 0, 0
            
        overhead_yellow = 5
        overhead_safety_red = 3
        overhead_startup = 3
        total_overhead = overhead_yellow + overhead_safety_red + overhead_startup
        
        safe_lane_count = max(1, lane_count)
            
        if queue > 50:
            max_possible_clearance = int((allocated_green / avg_car_time) * safe_lane_count)
            cleared_cars = min(queue, max_possible_clearance)
            
            # STRAGGLER FLUSH
            if 0 < (queue - cleared_cars) <= safe_lane_count:
                cleared_cars = queue
                time_spent_moving = (cleared_cars / safe_lane_count) * avg_car_time
                allocated_green = max(allocated_green, time_spent_moving)
            else:
                time_spent_moving = (cleared_cars / safe_lane_count) * avg_car_time
        else:
            time_spent_moving = 0.0
            cleared_cars = 0
            while cleared_cars < queue:
                car_time = random.uniform(max(0.5, avg_car_time - 0.5), avg_car_time + 0.5)
                if time_spent_moving + car_time <= allocated_green:
                    cleared_cars += min(safe_lane_count, queue - cleared_cars)
                    time_spent_moving += car_time
                else:
                    uncleared_temp = queue - cleared_cars
                    if uncleared_temp <= safe_lane_count:
                        cleared_cars += uncleared_temp
                        time_spent_moving += car_time
                        allocated_green = max(allocated_green, time_spent_moving)
                    break 
        
        uncleared = queue - cleared_cars
        
        if can_cut_early:
            used_green = time_spent_moving if uncleared == 0 else allocated_green
            wasted_green = used_green - time_spent_moving if uncleared == 0 else 0
        else:
            used_green = allocated_green
            wasted_green = allocated_green - time_spent_moving if uncleared == 0 else 0
                
        total_phase_time = used_green + total_overhead
        return uncleared, int(round(total_phase_time)), int(round(wasted_green)), int(round(used_green)), total_overhead

@app.route('/api/simulate', methods=['POST', 'GET'])
def simulate():
    if request.method == 'GET':
        return jsonify({"status": "SUCCESS! Arterial Flushing Live!"})

    try:
        data = request.json
        total_cycles = int(data.get('total_cycles', 50))
        avg_car_time = float(data.get('avg_car_time', 2.5)) 
        arrivals_per_min = data.get('arrivals_per_min', {"North": [1, 5], "South": [1, 5], "East": [2, 8], "West": [2, 8]})
        raw_lanes = data.get('lanes', {"NS": 3, "EW": 3})
        lanes_config = {"NS": max(1, int(raw_lanes.get("NS", 3) or 3)), "EW": max(1, int(raw_lanes.get("EW", 3) or 3))}
        
        ev_probs = data.get('ev_probs', {"North": 0.05, "South": 0.05, "East": 0.05, "West": 0.05})
        user_fx_times = data.get('fx_times', {"North": 45, "South": 45, "East": 60, "West": 60})

        sim = RealisticTrafficOptimizer()
        log_data_ai = []
        log_data_fx = []

        for cycle in range(1, total_cycles + 1):
            sim.fx_times = user_fx_times.copy()
            ai_cycle_mins = max(0.25, sim.last_ai_cycle_time / 60.0)
            fx_cycle_mins = max(0.25, sim.last_fx_cycle_time / 60.0)

            new_arrivals_ai = {}
            new_arrivals_fx = {}
            
            for lane in sim.lanes:
                ai_cars = sim.generate_arrivals(lane, arrivals_per_min, ai_cycle_mins)
                new_arrivals_ai[lane] = ai_cars
                sim.ai_queues[lane] += ai_cars
                
                fx_cars = sim.generate_arrivals(lane, arrivals_per_min, fx_cycle_mins)
                new_arrivals_fx[lane] = fx_cars
                sim.fx_queues[lane] += fx_cars

            for lane in sim.lanes:
                lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
                target_time = sim.ml_agent.get_action(lane, sim.ai_queues[lane], lane_count, avg_car_time)
                if sim.emergency_cooldowns[lane] > 0:
                    target_time += 15
                    sim.emergency_cooldowns[lane] -= 1
                sim.ai_times[lane] = target_time

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

            ai_phase_results = {}
            total_ai_used_time = 0
            for lane in ai_execution_order:
                q = sim.ai_queues[lane]
                alloc = sim.ai_times[lane]
                lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
                
                ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
                if ev_data: 
                    effective_pos = max(1, ev_data["pos_ai"] // lane_count)
                    alloc = max(alloc, int(effective_pos * (avg_car_time + 1)))
                
                unc, total_used, wst, used_green, overhead = sim.simulate_lane_traffic(lane, q, alloc, avg_car_time, True, lane_count)
                
                ai_phase_results[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': total_used, 'wst': wst, 'green': used_green, 'overhead': overhead, 'ev': ev_data}
                total_ai_used_time += total_used

            sim.last_ai_cycle_time = total_ai_used_time

            fx_phase_results = {}
            total_fx_used_time = 0
            for lane in fx_execution_order:
                q = sim.fx_queues[lane]
                alloc = sim.fx_times[lane]
                lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
                ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
                
                unc, total_used, wst, used_green, overhead = sim.simulate_lane_traffic(lane, q, alloc, avg_car_time, False, lane_count)
                
                fx_phase_results[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': total_used, 'wst': wst, 'green': used_green, 'overhead': overhead, 'ev': ev_data}
                total_fx_used_time += total_used
                
            sim.last_fx_cycle_time = total_fx_used_time

            def calculate_exact_loss(lane, res, red_time, is_ai, current_new_arrivals):
                effective_fail_red = max(45, red_time)
                holdovers = max(0, res['q'] - current_new_arrivals[lane])
                new_arrived = current_new_arrivals[lane]
                
                penalty_holdover = red_time 
                penalty_new = red_time / 2.0 
                if red_time > 60:
                    escalation = (red_time - 60) * 1.25
                    penalty_holdover += escalation
                    penalty_new += escalation
                    
                loss_waiting = (holdovers * penalty_holdover) + (new_arrived * penalty_new)
                loss_failed = res['unc'] * (effective_fail_red * 1.5)
                loss_queue = res['q'] * 5.0
                loss_starve = (holdovers ** 2) * 5.0 
                
                total_loss = loss_waiting + loss_failed + loss_queue + loss_starve
                if is_ai: sim.ml_agent.backpropagate(lane, res['unc'], res['wst'], holdovers)
                return int(total_loss), int(loss_waiting), int(loss_failed), int(loss_queue), int(loss_starve), int(red_time)

            for phase_step, lane in enumerate(ai_execution_order, 1):
                res = ai_phase_results[lane]
                red_time = max(0, total_ai_used_time - res['used'])
                loss, l_wait, l_fail, l_queue, l_starve, true_red = calculate_exact_loss(lane, res, red_time, True, new_arrivals_ai)
                sim.ai_total_loss += loss
                sim.ai_queues[lane] = res['unc']
                event_ai = f"{res['ev']['icon']} {res['ev']['type']} (Pos {res['ev']['pos_ai']}) ✅ | " if res['ev'] else ("⚡ Recovery | " if sim.emergency_cooldowns[lane] > 0 else "")
                if res['alloc'] == 0: timing_str = "⏭️ Skipped (Empty)"
                else: timing_str = f"🟩 {res['alloc']}s ✂️ {res['green']}s (+11s 🚦)" if res['green'] < res['alloc'] else f"🟩 {res['alloc']}s (+11s 🚦)"

                log_data_ai.append({
                    "Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": timing_str, 
                    "Queue": str(res['q']), "Cycle Loss": loss, "Events": event_ai,
                    "Arrivals": new_arrivals_ai[lane], "Failed": res['unc'], "Wasted": res['wst'],
                    "LossWait": l_wait, "LossFail": l_fail, "LossQueue": l_queue, "LossStarve": l_starve, "RedTime": true_red
                })

            for phase_step, lane in enumerate(fx_execution_order, 1):
                res = fx_phase_results[lane]
                red_time = max(0, total_fx_used_time - res['used'])
                loss, l_wait, l_fail, l_queue, l_starve, true_red = calculate_exact_loss(lane, res, red_time, False, new_arrivals_fx)
                sim.fx_total_loss += loss
                sim.fx_queues[lane] = res['unc']
                
                event_fx = ""
                if res['ev']:
                    lane_count = lanes_config["NS"] if lane in ["North", "South"] else lanes_config["EW"]
                    req = max(1, int(res['ev']['pos_fx'] // lane_count)) * (avg_car_time + 1)
                    event_fx = f"{res['ev']['icon']} {res['ev']['type']} (Pos {res['ev']['pos_fx']}) " + ("⚠️ Lucky | " if res['alloc'] >= req else "❌ STRANDED! | ")
                
                timing_str = "⏭️ Skipped" if res['alloc'] == 0 else f"🟩 {res['alloc']}s (+11s 🚦)"

                log_data_fx.append({
                    "Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": f"{res['alloc']}s", 
                    "Queue": str(res['q']), "Cycle Loss": loss, "Events": event_fx,
                    "Arrivals": new_arrivals_fx[lane], "Failed": res['unc'], "Wasted": res['wst'],
                    "LossWait": l_wait, "LossFail": l_fail, "LossQueue": l_queue, "LossStarve": l_starve, "RedTime": true_red
                })

        return jsonify({"ai_logs": log_data_ai, "fx_logs": log_data_fx})
        
    except Exception as e:
        error_msg = f"Python Crash: {str(e)} | Trace: {traceback.format_exc()}"
        return jsonify({"error": error_msg}), 500
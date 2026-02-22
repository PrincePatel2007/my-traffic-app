from flask import Flask, request, jsonify
import random

app = Flask(__name__)

class RealisticTrafficOptimizer:
    def __init__(self):
        self.lanes = ["North", "South", "East", "West"]
        # Starting times for both systems
        self.ai_times = {"North": 45, "South": 45, "East": 60, "West": 60}
        self.fx_times = {"North": 45, "South": 45, "East": 60, "West": 60}
        
        self.ai_queues = {lane: 0 for lane in self.lanes}
        self.fx_queues = {lane: 0 for lane in self.lanes}
        
        # AI Tuning Parameters
        self.max_shift_per_cycle = 10  # Max seconds AI can add/remove per normal cycle
        self.recovery_jump = 25        # Fast recovery shift after an Emergency Vehicle
        self.emergency_cooldowns = {lane: 0 for lane in self.lanes}
        
        self.ai_total_loss = 0
        self.fx_total_loss = 0

    def generate_arrivals(self, lane, arrival_ranges):
        prob = random.random()
        arr_range = arrival_ranges[lane]
        # 10% chance of a random massive spike in traffic
        spike_max = int(arr_range[1] * 1.5) + 1
        return random.randint(arr_range[1], spike_max) if prob < 0.10 else random.randint(arr_range[0], arr_range[1])

    def process_lane(self, lane, queue, max_green_time, red_time, avg_car_time):
        time_spent = 0
        cleared_cars = 0
        for _ in range(queue):
            # Give a little random variance to how long a car takes to cross (+/- 1 second)
            car_time = random.randint(max(1, avg_car_time - 1), avg_car_time + 1)
            if time_spent + car_time <= max_green_time:
                cleared_cars += 1
                time_spent += car_time
            else:
                break 
        
        uncleared = queue - cleared_cars
        
        # Calculate wasted time if the queue empties early
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
            
        loss = actual_wasted + (uncleared * red_time)
        return uncleared, actual_wasted, loss, actual_green_used

    def calculate_proportional_targets(self, queues, total_cycle_time=150):
        """
        NEW INDIAN-CONTEXT AI LOGIC:
        Simulates an overhead camera network (Computer Vision).
        It calculates the exact density of the intersection and allocates
        green time strictly based on the proportion of cars in each lane.
        """
        targets = {}
        total_cars = sum(queues.values())
        
        # If intersection is totally empty, default to safe minimums
        if total_cars == 0:
            return {lane: 30 for lane in self.lanes}
            
        for lane in self.lanes:
            # Calculate the percentage of total traffic sitting in this lane
            lane_ratio = queues[lane] / total_cars
            
            # Allocate time proportionally, but enforce a 15s minimum and 100s maximum
            calculated_time = int(lane_ratio * total_cycle_time)
            targets[lane] = max(15, min(100, calculated_time))
            
        return targets

@app.route('/api/simulate', methods=['POST', 'GET'])
def simulate():
    # VERCEL CLOUD SAFETY CHECK
    if request.method == 'GET':
        return jsonify({"status": "SUCCESS! The Python AI Engine is live!"})

    # START ACTUAL SIMULATION
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
        
        # Reset Fixed times manually every cycle (It refuses to adapt)
        sim.fx_times["North"] = manual_ns
        sim.fx_times["South"] = manual_ns
        sim.fx_times["East"] = manual_ew
        sim.fx_times["West"] = manual_ew
        
        # Cycle 1 Smart Start
        if cycle == 1:
            for lane in sim.lanes:
                expected_vehicles = sum(arrival_ranges[lane]) / 2.0
                smart_starting_time = int((expected_vehicles * avg_car_time) + 5)
                sim.ai_times[lane] = max(15, min(160, smart_starting_time))

        total_ai_cycle_time = sum(sim.ai_times.values())
        total_fx_cycle_time = sum(sim.fx_times.values())

        # Generate new cars entering the intersection
        for lane in sim.lanes:
            new_cars = sim.generate_arrivals(lane, arrival_ranges)
            sim.ai_queues[lane] += new_cars
            sim.fx_queues[lane] += new_cars

        # Emergency Vehicle (EV) Preemption Logic
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
            event_ai = "Normal"
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            
            # AI instantly extends green light to guarantee EV clears
            if ev_data:
                safe_car_time = avg_car_time + 1 
                max_ai_time = max(max_ai_time, ev_data["pos_ai"] * safe_car_time)
                event_ai = f"{ev_data['icon']} {ev_data['type']} EVP (@ Pos {ev_data['pos_ai']}): ✅ CLEARED"
            elif sim.emergency_cooldowns[lane] > 0:
                event_ai = "⚡ Post-EVP Recovery"

            ai_fail, ai_waste, ai_l, ai_used_time = sim.process_lane(lane, q_before_ai, max_ai_time, total_ai_cycle_time - max_ai_time, avg_car_time)
            sim.ai_queues[lane] = ai_fail
            sim.ai_total_loss += ai_l

            timing_str_ai = f"{max_ai_time}s ✂️ Cut to {ai_used_time}s" if ai_used_time < max_ai_time else f"{max_ai_time}s"
            if max_ai_time != base_ai_time: timing_str_ai = f"🚨 {timing_str_ai}"
            queue_display_ai = f"🛑 {q_before_ai} 🚗💥" if q_before_ai > 50 else str(q_before_ai)

            log_data_ai.append({"Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": timing_str_ai, "Queue": queue_display_ai, "Cycle Loss": ai_l, "Events": event_ai})

        # PROCESS FIXED SYSTEM
        for phase_step, lane in enumerate(fx_execution_order, 1):
            q_before_fx = sim.fx_queues[lane]
            max_fx_time = sim.fx_times[lane]
            event_fx = "Normal"
            ev_data = next((ev for ev in active_evs if ev["lane"] == lane), None)
            
            # Fixed system just hopes the EV makes it
            if ev_data:
                req_time_fx = ev_data["pos_fx"] * (avg_car_time + 1)
                event_fx = f"{ev_data['icon']} {ev_data['type']} (@ Pos {ev_data['pos_fx']}): " + ("⚠️ Lucky Cleared" if max_fx_time >= req_time_fx else "❌ STRANDED!")

            fx_fail, fx_waste, fx_l, fx_used_time = sim.process_lane(lane, q_before_fx, max_fx_time, total_fx_cycle_time - max_fx_time, avg_car_time)
            sim.fx_queues[lane] = fx_fail
            sim.fx_total_loss += fx_l

            timing_str_fx = f"{max_fx_time}s ✂️ Cut to {fx_used_time}s" if fx_used_time < max_fx_time else f"{max_fx_time}s"
            queue_display_fx = f"🛑 {q_before_fx} 🚗💥" if q_before_fx > 50 else str(q_before_fx)

            log_data_fx.append({"Cycle": cycle, "Phase Sequence": f"{phase_step}. {lane}", "Allocated ➡️ Used": timing_str_fx, "Queue": queue_display_fx, "Cycle Loss": fx_l, "Events": event_fx})

        # ==========================================
        # 🧠 THE NEW AI BRAIN: PROPORTIONAL SHIFTING
        # ==========================================
        current_total_time = sum(sim.ai_times.values())
        target_times = sim.calculate_proportional_targets(sim.ai_queues, total_cycle_time=current_total_time)
        is_any_recovering = any(c > 0 for c in sim.emergency_cooldowns.values())
        
        for lane in sim.lanes:
            difference = target_times[lane] - sim.ai_times[lane]
            
            if is_any_recovering and sim.emergency_cooldowns[lane] > 0:
                shift = max(-sim.recovery_jump, min(sim.max_shift_per_cycle, difference))
            else:
                shift = max(-sim.max_shift_per_cycle, min(sim.max_shift_per_cycle, difference))
                
            sim.ai_times[lane] += shift
            
            # Keep times realistic (between 15 and 160 seconds)
            sim.ai_times[lane] = max(15, min(160, sim.ai_times[lane]))
            
            if sim.emergency_cooldowns[lane] > 0: 
                sim.emergency_cooldowns[lane] -= 1

    return jsonify({"ai_logs": log_data_ai, "fx_logs": log_data_fx})
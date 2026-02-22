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
        
        if can_cut_early:
            if uncleared == 0:
                used_time = min(allocated_time, time_spent + 3)
            else:
                used_time = allocated_time
            wasted = used_time - time_spent if uncleared == 0 else 0
        else:
            used_time = allocated_time
            wasted = allocated_time - time_spent if uncleared == 0 else 0
                
        return uncleared, used_time, wasted

    def ask_gemini_for_targets(self, stats, avg_car_time):
        targets = {}
        for l in self.lanes:
            current = self.ai_times[l]
            adjust = (stats[l]["failed"] * avg_car_time * 2.0) - (stats[l]["wasted"] * 0.25)
            targets[l] = max(15, min(160, int(current + adjust)))
        return targets

@app.route('/api/simulate', methods=['POST', 'GET'])
def simulate():
    if request.method == 'GET':
        return jsonify({"status": "Backend Live"})

    data = request.json
    total_cycles = data.get('total_cycles', 50)
    avg_car_time = data.get('avg_car_time', 5)
    arrival_ranges = data.get('arrival_ranges', {"North": [2, 12], "South": [2, 12], "East": [5, 15], "West": [5, 15]})
    ev_probs = data.get('ev_probs', {"North": 0.05, "South": 0.05, "East": 0.05, "West": 0.05})

    sim = RealisticTrafficOptimizer()
    log_data_ai, log_data_fx = [], []
    manual_ns, manual_ew = 45, 60

    for cycle in range(1, total_cycles + 1):
        cycle_stats_ai = {}
        sim.fx_times = {"North": manual_ns, "South": manual_ns, "East": manual_ew, "West": manual_ew}
        
        if cycle == 1:
            for lane in sim.lanes:
                expected = sum(arrival_ranges[lane]) / 2.0
                sim.ai_times[lane] = max(15, min(160, int((expected * avg_car_time) + 5)))

        new_arrivals = {lane: sim.generate_arrivals(lane, arrival_ranges) for lane in sim.lanes}
        for lane in sim.lanes:
            sim.ai_queues[lane] += new_arrivals[lane]
            sim.fx_queues[lane] += new_arrivals[lane]

        ev_icons = {"Ambulance": "🚑", "Fire Truck": "🚒", "Police Car": "🚓"}
        active_evs = []
        for lane in sim.lanes:
            if random.random() < ev_probs[lane]: 
                ev_type = random.choice(list(ev_icons.keys()))
                active_evs.append({"lane": lane, "type": ev_type, "icon": ev_icons[ev_type], "pos_ai": random.randint(1, max(1, sim.ai_queues[lane])), "pos_fx": random.randint(1, max(1, sim.fx_queues[lane]))})
                sim.emergency_cooldowns[lane] = 3 

        ai_order = [ev["lane"] for ev in active_evs] + [l for l in sim.lanes if l not in [e["lane"] for e in active_evs]]
        fx_order = ["North", "South", "East", "West"]

        # PRE-CALC AI
        total_ai_used = 0
        ai_res = {}
        for lane in ai_order:
            q, alloc = sim.ai_queues[lane], sim.ai_times[lane]
            ev = next((e for e in active_evs if e["lane"] == lane), None)
            if ev: alloc = max(alloc, ev["pos_ai"] * (avg_car_time + 1))
            unc, used, wst = sim.simulate_lane_traffic(q, alloc, avg_car_time, True)
            ai_res[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': used, 'wst': wst, 'ev': ev}
            total_ai_used += used

        # PRE-CALC FX
        total_fx_used = sum(sim.fx_times.values())
        fx_res = {}
        for lane in fx_order:
            q, alloc = sim.fx_queues[lane], sim.fx_times[lane]
            ev = next((e for e in active_evs if e["lane"] == lane), None)
            unc, used, wst = sim.simulate_lane_traffic(q, alloc, avg_car_time, False)
            fx_res[lane] = {'q': q, 'alloc': alloc, 'unc': unc, 'used': alloc, 'wst': wst, 'ev': ev}

        # AI LOGS
        for step, lane in enumerate(ai_order, 1):
            r = ai_res[lane]
            red = total_ai_used - r['used']
            wait_pen = (max(0, r['q']-new_arrivals[lane])*red) + (new_arrivals[lane]*(red/2.0))
            loss = (r['wst']*5) + (r['unc']*(red*1.5)) + wait_pen
            sim.ai_total_loss += loss
            sim.ai_queues[lane] = r['unc']
            cycle_stats_ai[lane] = {"failed": r['unc'], "wasted": r['wst']}
            
            ev_str = f"{r['ev']['icon']} {r['ev']['type']} Cleared | " if r['ev'] else ("⚡ Recovery | " if sim.emergency_cooldowns[lane]>0 else "")
            log_data_ai.append({
                "Cycle": cycle, "Phase Sequence": f"{step}. {lane}", "Allocated ➡️ Used": f"{r['used']}s", 
                "Queue": str(r['q']), "Cycle Loss": int(loss), "Events": f"{ev_str}Avg Wait: {int(red/2)}s",
                "Arrivals": new_arrivals[lane], "Failed": r['unc'], "Wasted": r['wst'], "AvgWait": int(red/2), "WaitPenalty": int(wait_penalty := wait_pen)
            })

        # FX LOGS
        for step, lane in enumerate(fx_order, 1):
            r = fx_res[lane]
            red = total_fx_used - r['used']
            wait_pen = (max(0, r['q']-new_arrivals[lane])*red) + (new_arrivals[lane]*(red/2.0))
            loss = (r['wst']*5) + (r['unc']*(red*1.5)) + wait_pen
            sim.fx_total_loss += loss
            sim.fx_queues[lane] = r['unc']
            
            ev_str = f"{r['ev']['icon']} {r['ev']['type']} {'Lucky' if r['alloc']>=r['ev']['pos_fx']*(avg_car_time+1) else 'Stranded'} | " if r['ev'] else ""
            log_data_fx.append({
                "Cycle": cycle, "Phase Sequence": f"{step}. {lane}", "Allocated ➡️ Used": f"{r['alloc']}s", 
                "Queue": str(r['q']), "Cycle Loss": int(loss), "Events": f"{ev_str}Avg Wait: {int(red/2)}s",
                "Arrivals": new_arrivals[lane], "Failed": r['unc'], "Wasted": r['wst'], "AvgWait": int(red/2), "WaitPenalty": int(wait_pen)
            })

        # UPDATE AI
        targets = sim.ask_gemini_for_targets(cycle_stats_ai, avg_car_time)
        for lane in sim.lanes:
            diff = targets[lane] - sim.ai_times[lane]
            shift = max(-sim.recovery_jump, min(sim.max_shift_per_cycle, diff)) if sim.emergency_cooldowns[lane]>0 else max(-sim.max_shift_per_cycle, min(sim.max_shift_per_cycle, diff))
            sim.ai_times[lane] = max(15, min(160, sim.ai_times[lane] + shift))
            if sim.emergency_cooldowns[lane]>0: sim.emergency_cooldowns[lane] -= 1

    return jsonify({"ai_logs": log_data_ai, "fx_logs": log_data_fx})
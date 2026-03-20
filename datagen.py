import pandapower as pp
import pandapower.networks as pn
import pandas as pd
import numpy as np

n_samples = 1000
data = []

net = pn.case30()

for i in range(n_samples):
    # multiplying p_mw by a random factor
    random_scaling = np.random.uniform(0.8, 1.2, size=len(net.load))
    net.load.scaling = random_scaling

    # random N-1 outage
    random_line = np.random.choice(net.line.index)
    net.line.at[random_line, "in_service"] = False

    try:
        pp.runpp(net, enforce_q_lims=True)

        # checking violations
        v_max = net.res_bus.vm_pu.max()
        v_min = net.res_bus.vm_pu.min()
        has_violation = 1 if (v_max > 1.05 or v_min < 0.95) else 0

        # dict to store the outcome
        scenario_results = {
            "outage_line": random_line,
            "max_v_pu": v_max,
            "min_v_pu": v_min,
            "violation": has_violation,
            "total_demand_mw": net.load.p_mw.sum()
        }

        # load values of each bus
        for idx, load_val in enumerate(net.load.p_mw * net.load.scaling):
            scenario_results[f"load_bus_{net.load.bus.iloc[idx]}"] = load_val

        # adding generator setpoints
        for idx, gen_v in enumerate(net.gen.vm_pu):
            scenario_results[f"gen_{idx}_v_setpoint"] = gen_v
            
        data.append(scenario_results)

    except:
        pass

    df = pd.DataFrame(data)
    df.to_csv("generate_dataset.csv", index=False)


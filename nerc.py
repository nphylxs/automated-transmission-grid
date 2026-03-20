import pandapower as pp 
import pandapower.networks as pn

# loading the IEEE 30-bus 
network = pn.case30()

violations = []

for i in network.line.index:
    # trip one line
    network.line.at[i, "in_service"] = False

    try:
        # trying to run the power flow
        pp.runpp(network)

        # checking if any of the buses violate NERC standards
        v_max = network.res_bus.vm_pu.max()
        v_min = network.res_bus.vm_pu.min()
        
        if v_max > 1.05 or v_min < 0.95:
            violations.append(f"Line {i} failure causes voltage violation!")
    
    except pp.LoadflowNotConverged:
        violations.append(f"Line {i} failure causes System Collapse (Non-convergence)!")
    
    # reset the tripped line
    network.line.at[i, "in_service"] = True

print(f'Analysis complete. Found {len(violations)} critical contingencies.')

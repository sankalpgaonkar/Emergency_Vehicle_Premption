# Save this file as: project/src/run_with_sumo.py

import gymnasium as gym
from stable_baselines3 import PPO
import sumo_rl
import pandas as pd
import traci # Import the traci library directly

# --- CONFIGURATION ---
NET_FILE = 'project/sumo_files/jaipur.net.xml'
ROUTE_FILE = 'project/sumo_files/jaipur.rou.xml'
MODEL_PATH = "project/models/ppo_traffic_model_v3.zip"
CSV_PATH = "project/results/results_v3.csv"

# --- HELPER FUNCTION TO GET WAIT TIME DIRECTLY ---
def get_system_wait_time():
    """
    Retrieves the total waiting time of all vehicles in the network.
    This is a more direct and reliable method.
    """
    wait_time = 0
    vehicle_list = traci.vehicle.getIDList()
    for vehicle_id in vehicle_list:
        wait_time += traci.vehicle.getAccumulatedWaitingTime(vehicle_id)
    return wait_time

def main():
    print("Loading trained AI model...")
    model = PPO.load(MODEL_PATH)
    
    # We don't need the add_system_info from sumo-rl anymore
    env = gym.make('sumo-rl-v0',
                    net_file=NET_FILE,
                    route_file=ROUTE_FILE,
                    use_gui=True,
                    num_seconds=3600,
                    single_agent=True,
                    reward_fn='diff-waiting-time',
                    observation_class=sumo_rl.environment.observations.DefaultObservationFunction
                   )

    obs, info = env.reset()
    done = False
    
    timesteps = []
    wait_times = []
    
    print("Starting simulation with trained AI agent...")
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated

        # Use our new, direct function to get the waiting time
        total_wait_time = get_system_wait_time()
        
        # We'll just track the total cumulative waiting time for now
        timesteps.append(info.get('step', 0))
        wait_times.append(total_wait_time)

    env.close()
    
    print(f"Simulation finished. Saving results to {CSV_PATH}...")
    results_df = pd.DataFrame({
        'timestep': timesteps,
        'cumulative_wait_time': wait_times # Changed column name for clarity
    })
    results_df.to_csv(CSV_PATH, index=False)
    print("Results saved.")

if __name__ == '__main__':
    main()
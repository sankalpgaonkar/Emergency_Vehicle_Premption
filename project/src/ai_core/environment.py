import sumo_rl
import gymnasium as gym

def create_env():
    # This code uses the exact argument names from your environment
    env = gym.make('sumo-rl-v0',
                    net_file='project/sumo_files/jaipur.net.xml',
                    route_file='project/sumo_files/jaipur.rou.xml',
                    use_gui=False,  # Set to True for debugging, False for training
                    num_seconds=3600,
                    single_agent=True,
                    # From the inspect output, this is the correct argument for the reward
                    reward_fn='diff-waiting-time',
                    # This is the correct argument for the observation.
                    # We will use the default observation class that comes with it.
                    observation_class=sumo_rl.environment.observations.DefaultObservationFunction
                   )
    return env
from stable_baselines3 import PPO
from environment import create_env

# Create the environment
env = create_env()

# Instantiate the PPO model with a Multi-Layer Perceptron policy
model = PPO("MlpPolicy",
            env,
            verbose=1,
            tensorboard_log="./tensorboard_logs/")

# Start the training process (this will take several hours)
# The more timesteps, the smarter the agent. Start with 100k for a first pass.
model.learn(total_timesteps=1000000)

# Save the trained model
model.save("project/models/ppo_traffic_model_v3")

print("Training complete and model saved.")
env.close()
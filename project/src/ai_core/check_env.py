# Save this as check_env.py
import inspect
import sumo_rl

# This will print the exact list of arguments the SumoEnvironment class expects.
print(inspect.getfullargspec(sumo_rl.SumoEnvironment.__init__))
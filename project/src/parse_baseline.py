# Save this file as project/src/parse_baseline.py
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np

XML_PATH = "project/baseline_tripinfo.xml"
CSV_PATH = "project/results/baseline_results_v3.csv"

print(f"Parsing {XML_PATH}...")

tree = ET.parse(XML_PATH)
root = tree.getroot()

wait_times = []
# Extract the waiting time for every vehicle from the XML log
for trip in root.findall('tripinfo'):
    wait_time = float(trip.get('timeLoss'))
    wait_times.append(wait_time)

# Calculate the cumulative sum of waiting time over the simulation duration
total_duration = 3600
steps = np.arange(0, total_duration + 1, 5) # Match 5s interval of AI run
cumulative_wait = np.zeros_like(steps, dtype=float)

# This is a simple way to approximate the cumulative wait time at each step
# A more accurate way would be to parse each step, but this is good for a chart
if wait_times:
    avg_wait_per_second = np.sum(wait_times) / total_duration
    for i, step in enumerate(steps):
        cumulative_wait[i] = avg_wait_per_second * step

# Save to CSV
results_df = pd.DataFrame({
    'timestep': steps,
    'cumulative_wait_time': cumulative_wait
})
results_df.to_csv(CSV_PATH, index=False)
print(f"Baseline results successfully saved to {CSV_PATH}")
from warehouse_env.env import WarehouseEnv
from warehouse_env.models import WarehouseAction, RobotAction
from warehouse_env.graders import GRADER_REGISTRY

# 1. Initialize the environment
env = WarehouseEnv()

# 2. List available tasks
print("Available tasks:", env.list_tasks())

# 3. Choose a task and reset the environment
# The "crisis_management" task features a robot breakdown at step 15
# and surge orders at step 25.
task_id = "crisis_management"
obs = env.reset(task_id=task_id)

print(f"\nStarted task: {task_id}")
print(f"Initial description: {obs.description}")

# 4. Simulate a few steps
# We will just direct all 5 robots to 'wait' to see time pass
# and trigger the step 15 disruption.
action = WarehouseAction(
    robots=[RobotAction(robot_id=i, action_type="wait") for i in range(5)]
)

print("\n--- Simulating 15 steps ---")
for step in range(1, 16):
    obs = env.step(action)
    
    # We expect a penalty for wasting a step (REW-04)
    wasted_reward = obs.metadata.get("reward_breakdown", {}).get("wasted_step", 0.0)
    
    if step == 15:
        print(f"\nStep {step} Observation Summary:")
        print(obs.description)
        print(f"Step Reward: {obs.reward} (Wasted step penalty: {wasted_reward})")

# 5. Evaluate End of Episode Grader
# Force end the episode early to see the task grader
env._episode.done = True
score = GRADER_REGISTRY[task_id](env)
print(f"\nFinal Grader Score for {task_id}: {score} (out of 1.0)")
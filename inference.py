import os, sys, json

_REQUIRED = ["API_BASE_URL", "MODEL_NAME", "HF_TOKEN"]
_missing = [v for v in _REQUIRED if not os.environ.get(v)]
if _missing:
    raise EnvironmentError(f"Missing required env vars: {', '.join(_missing)}")

API_BASE_URL = os.environ["API_BASE_URL"]
MODEL_NAME   = os.environ["MODEL_NAME"]
HF_TOKEN     = os.environ["HF_TOKEN"]

from openai import OpenAI
from warehouse_env.env import WarehouseEnv
from warehouse_env.models import WarehouseAction, RobotAction
from warehouse_env.graders import GRADER_REGISTRY
from warehouse_env.tasks import TASK_REGISTRY

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

PROMPT_TEMPLATE = (
    "You are controlling warehouse robots. Current state:\n"
    "{description}\n\n"
    'Return a JSON array of actions for each active robot. Each action: {{"robot_id": <int>, "action_type": "<move_up|move_down|move_left|move_right|pick|drop|wait>"}}\n'
    "Only include active robots. Example: [{\"robot_id\": 0, \"action_type\": \"move_down\"}]\n\n"
    "Actions JSON:\n"
)

def get_actions(obs, active_robot_ids: list[int]) -> tuple[WarehouseAction, str | None]:
    """Call LLM once for all active robots. Returns (action, error_msg_or_None)."""
    prompt = PROMPT_TEMPLATE.format(description=obs.description)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.0,
        )
        text = response.choices[0].message.content or ""
        start = text.find("[")
        end   = text.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON array found in response")
        parsed = json.loads(text[start:end])
        robot_actions = [
            RobotAction(robot_id=a["robot_id"], action_type=a["action_type"])
            for a in parsed
            if a.get("robot_id") in active_robot_ids
        ]
        return WarehouseAction(robots=robot_actions), None
    except Exception as exc:
        wait_actions = [RobotAction(robot_id=rid, action_type="wait") for rid in active_robot_ids]
        return WarehouseAction(robots=wait_actions), str(exc)

def run_task(env: WarehouseEnv, task_id: str) -> None:
    task_config = TASK_REGISTRY[task_id]
    obs = env.reset(task_id=task_id)
    all_rewards: list[float] = []

    # [START] line — per D-07
    print(f"[START] task={task_id} env=warehouse model={MODEL_NAME}", flush=True)

    for step_num in range(1, task_config.max_steps + 1):
        active_ids = [r.id for r in obs.robots if r.is_active]
        action, error_msg = get_actions(obs, active_ids)

        obs, reward, done, _info = env.step(action)
        all_rewards.append(reward)

        # action= field: comma-joined action_types from the action we sent
        action_str = ",".join(a.action_type for a in action.robots) if action.robots else "wait"
        error_field = error_msg if error_msg else "null"

        # [STEP] line — per D-07
        print(
            f"[STEP] step={step_num} action={action_str} reward={reward:.2f} "
            f"done={str(done).lower()} error={error_field}",
            flush=True,
        )

        if done:
            break

    # Score via grader registry (D-10)
    score = GRADER_REGISTRY[task_id](env)

    # success = score > 0 (D-08)
    success = score > 0.0

    # rewards = comma-joined all step rewards rounded to 2dp (D-08)
    rewards_str = ",".join(f"{r:.2f}" for r in all_rewards)

    # [END] line — per D-07
    print(
        f"[END] success={str(success).lower()} steps={len(all_rewards)} "
        f"score={score:.2f} rewards={rewards_str}",
        flush=True,
    )

if __name__ == "__main__":
    env = WarehouseEnv()
    for task_id in ["solo_delivery", "coordinated_delivery", "crisis_management"]:
        run_task(env, task_id)

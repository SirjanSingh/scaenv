import os
from openai import OpenAI

client = OpenAI(
    base_url=os.environ.get("API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    api_key=os.environ.get("HF_TOKEN")
)

prompt = """You are controlling warehouse robots. Current state:
Task: solo_delivery. Step 1/100. Robot 0 at (3,5) idle. 5 of 5 orders remaining.

Return a JSON array of actions for each active robot. Each action: {"robot_id": <int>, "action_type": "<move_up|move_down|move_left|move_right|pick|drop|wait>"}
Only include active robots. Example: [{"robot_id": 0, "action_type": "move_down"}]
Return ONLY a valid JSON array. Do not use markdown blocks.

Actions JSON:
"""

response = client.chat.completions.create(
    model=os.environ.get("MODEL_NAME", "gemini-2.5-flash"),
    messages=[{"role": "user", "content": prompt}],
    temperature=0.0
)

print("Finish reason:", response.choices[0].finish_reason)
print("Content:", repr(response.choices[0].message.content))

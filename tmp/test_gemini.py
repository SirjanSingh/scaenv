import os
from openai import OpenAI

client = OpenAI(
    base_url=os.environ.get("API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    api_key=os.environ.get("HF_TOKEN")
)

response = client.chat.completions.create(
    model=os.environ.get("MODEL_NAME", "gemini-2.5-flash"),
    messages=[{"role": "user", "content": "Return a JSON array with robot_id 0 and action move_down"}],
    temperature=0.0,
    max_tokens=256
)

print("Finish reason:", response.choices[0].finish_reason)
print("Content:", repr(response.choices[0].message.content))

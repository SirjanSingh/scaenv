# Extensive Run Guide: WarehouseEnv

This guide provides a detailed, step-by-step tutorial on how to install, run, and benchmark the `WarehouseEnv` project.

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Local Installation](#2-local-installation)
3. [Running the OpenEnv API Server](#3-running-the-openenv-api-server)
4. [Using Docker (Recommended)](#4-using-docker-recommended)
5. [Running the LLM Inference Agent](#5-running-the-llm-inference-agent)
6. [Testing the API Manually](#6-testing-the-api-manually)

---

## 1. Prerequisites

Before running the project locally, ensure you have:
- **Python 3.11** or newer.
- **pip** package manager.
- **Docker** (optional, but highly recommended for containerized testing).
- An API Key for a Hugging Face supported model / OpenAI-compatible endpoint (required only if running the `inference.py` agent).

---

## 2. Local Installation

If you prefer to run the server directly on your operating system, you can perform an editable installation. This will install all dependencies (FastAPI, Uvicorn, Pydantic).

```bash
# Clone the repository and cd into it
git clone https://github.com/SirjanSingh/scaenv.git
cd scaenv

# (Optional) Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install the environment locally
pip install -e .
```

---

## 3. Running the OpenEnv API Server

The project exposes a REST API via FastAPI that complies with the OpenEnv specification (`POST /reset` and `POST /step`).

**Starting the server:**

```bash
# Option 1: Using the entry point
server

# Option 2: Using uvicorn directly
uvicorn server.app:app --host 0.0.0.0 --port 7860
```
By default, the server listens on **port 7860** (the required port for Hugging Face Spaces).

---

## 4. Using Docker (Recommended)

Running via Docker ensures you exactly mimic the Hugging Face Space deployment environment.

**Build the image:**
```bash
# Build the python:3.11-slim based image
docker build -t warehouse-env .
```

**Run the container:**
```bash
# Bind the container's 7860 port to your host machine's 7860 port
docker run -p 7860:7860 warehouse-env
```
The API is now accessible at `http://localhost:7860`.

---

## 5. Running the LLM Inference Agent

The `inference.py` script executes an end-to-end evaluation. It starts the LLM, connects to the local server (via `http://localhost:7860`), and loops through all three tasks. 

To run it, configure your model environment variables:

```bash
# Windows (PowerShell)
$env:API_BASE_URL="https://api-inference.huggingface.co/v1"
$env:MODEL_NAME="meta-llama/Llama-3.1-8B-Instruct"
$env:HF_TOKEN="hf_YOUR_TOKEN_HERE"

# Linux / macOS
export API_BASE_URL="https://api-inference.huggingface.co/v1"
export MODEL_NAME="meta-llama/Llama-3.1-8B-Instruct"
export HF_TOKEN="hf_YOUR_TOKEN_HERE"
```

Then execute the script:
```bash
python inference.py
```
You will see the script output `[START]`, `[STEP]`, and `[END]` blocks, representing the standard OpenEnv inference logging protocol.

---

## 6. Testing the API Manually

If you wish to test the server logic directly without the LLM, you can use `curl` to interact with the endpoints.

**Start a new episode:**
```bash
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "solo_delivery"}'
```

**Execute a step:**
```bash
# Instruct Robot 0 to move down
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{
    "action": {
      "robots": [{"robot_id": 0, "action_type": "move_down"}]
    }
  }'
```
You should receive a JSON response containing the updated grid state, active tasks, and reward values.

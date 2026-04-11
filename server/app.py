from openenv.core.env_server.http_server import create_app
from warehouse_env.models import WarehouseAction, WarehouseObservation
from warehouse_env.env import WarehouseEnv

# Singleton env instance — persists episode state between HTTP reset/step calls
# Using lambda: _env_instance so create_app factory pattern is satisfied
# per research Pitfall 5: fresh env per request loses episode state
_env_instance = WarehouseEnv()

app = create_app(
    lambda: _env_instance,
    WarehouseAction,
    WarehouseObservation,
    env_name="warehouse_env",
    max_concurrent_envs=1,
)


# Health check endpoint for Cloud Run startup probes and monitoring
@app.get("/health")
def health():
    return {"status": "healthy"}


def main(host: str = "0.0.0.0", port: int | None = None):
    import os, uvicorn
    resolved_port = port if port is not None else int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host=host, port=resolved_port)


if __name__ == "__main__":
    main()

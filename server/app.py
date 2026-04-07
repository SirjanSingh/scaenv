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


def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

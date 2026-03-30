"""Entrypoint script that populates YAML config templates from environment
variables and Clowder ACG config, then starts lightspeed-stack."""

import os

import yaml

TEMPLATE_DIR = "/app"
RUNTIME_DIR = "/app-root"
RUN_YAML = "run.yaml"
STACK_YAML = "lightspeed-stack.yaml"


def load_clowder_config():
    """Load Clowder ACG config if CLOWDER_ENABLED is set."""
    if not os.environ.get("CLOWDER_ENABLED", "").lower() in ("true", "1", "yes"):
        print("[entrypoint] CLOWDER_ENABLED not set, skipping Clowder config")
        return None

    from app_common_python import LoadedConfig

    print("[entrypoint] Clowder config loaded")
    return LoadedConfig


def apply_clowder_config(run_config, stack_config, clowder):
    """Apply Clowder ACG config values to the parsed YAML configs."""
    if clowder is None:
        return run_config, stack_config

    # Database config - switch from sqlite to postgres if DB is available
    if clowder.database:
        db = clowder.database
        db_url = (
            f"postgresql://{db.username}:{db.password}"
            f"@{db.hostname}:{db.port}/{db.name}"
        )
        ssl_mode = getattr(db, "sslMode", None)
        if ssl_mode:
            db_url += f"?sslmode={ssl_mode}"

        print(f"[entrypoint] Using Clowder DB: {db.hostname}:{db.port}/{db.name}")

        # Update storage backends from sqlite to postgres
        storage = run_config.get("storage", {})
        backends = storage.get("backends", {})

        backends["kv_default"] = {
            "type": "kv_postgres",
            "db_path": db_url,
        }
        backends["sql_default"] = {
            "type": "sql_postgres",
            "db_path": db_url,
        }

        # Update conversation cache in stack config
        stack_config["conversation_cache"] = {
            "type": "postgres",
            "postgres": {
                "db_url": db_url,
            },
        }

    return run_config, stack_config


def render_configs(clowder):
    """Read template YAMLs, apply Clowder config, write to runtime dir."""
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    run_template = os.path.join(TEMPLATE_DIR, RUN_YAML)
    stack_template = os.path.join(TEMPLATE_DIR, STACK_YAML)

    with open(run_template) as f:
        run_config = yaml.safe_load(f)

    with open(stack_template) as f:
        stack_config = yaml.safe_load(f)

    run_config, stack_config = apply_clowder_config(run_config, stack_config, clowder)

    run_out = os.path.join(RUNTIME_DIR, RUN_YAML)
    stack_out = os.path.join(RUNTIME_DIR, STACK_YAML)

    with open(run_out, "w") as f:
        yaml.dump(run_config, f, default_flow_style=False, sort_keys=False)

    with open(stack_out, "w") as f:
        yaml.dump(stack_config, f, default_flow_style=False, sort_keys=False)

    print(f"[entrypoint] Wrote {run_out}")
    print(f"[entrypoint] Wrote {stack_out}")


def main():
    clowder = load_clowder_config()
    render_configs(clowder)

    # Exec lightspeed-stack
    print("[entrypoint] Starting lightspeed-stack...")
    os.execvp("python3.12", ["python3.12", "src/lightspeed_stack.py"])


if __name__ == "__main__":
    main()

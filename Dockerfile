FROM registry.redhat.io/lightspeed-core/lightspeed-stack-rhel9:latest

USER root

# Install uv and entrypoint dependencies
RUN pip3.12 install "uv>=0.8.15" && \
    uv pip install --python /app-root/.venv/bin/python --index-url https://pypi.org/simple/ app-common-python pyyaml

USER 1001

# Copy YAML templates and entrypoint script
COPY run.yaml lightspeed-stack.yaml /app/
COPY entrypoint.py /app/

ENTRYPOINT ["python3.12", "/app/entrypoint.py"]

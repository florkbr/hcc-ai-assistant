FROM registry.redhat.io/lightspeed-core/lightspeed-stack-rhel9:f271b085e4c77f2f9af92d43dc0a37afe7036748

USER root

# Install uv and entrypoint dependencies
RUN pip3.12 install "uv>=0.8.15" && \
    uv pip install --python /app-root/.venv/bin/python --index-url https://pypi.org/simple/ app-common-python pyyaml

# OpenShift runs containers with a random UID in group 0 (root).
# Make /app-root writable by group 0 so the entrypoint can write rendered configs.
RUN chgrp -R 0 /app-root && chmod -R g=u /app-root

USER 1001

# Copy YAML templates, entrypoint, and reverse proxy
COPY run.yaml lightspeed-stack.yaml /app/
COPY entrypoint.py proxy.py /app/

ENTRYPOINT ["python3.12", "/app/entrypoint.py"]

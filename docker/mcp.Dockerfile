FROM python:3.12-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt* /srv/
RUN if [ -f requirements.txt ]; then \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . /srv

ENV PORT=8081
# Allow overriding the start command via env
ENV MCP_START_CMD="python -m mcp.run_enhanced_mcp_server_with_guidelines"

CMD ["bash", "-lc", "${MCP_START_CMD} --host 0.0.0.0 --port ${PORT}"]

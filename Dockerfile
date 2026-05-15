# MK Spec Master container — built primarily so Glama (and any other MCP
# catalog that introspects servers in a sandbox) can boot the server,
# send `initialize` + `tools/list` over stdio, and confirm a clean
# JSON-RPC response.
#
# Day-to-day use stays `uvx mk-spec-master` on the host: real spec
# fetches need access to the user's repo, network for Linear/JIRA APIs,
# and credentials that live outside any sane container.

FROM python:3.12-slim

# Install from local source so the image always reflects the current
# commit (introspection should pass even before a PyPI release).
WORKDIR /srv
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Defaults for the introspection probe. SPEC_PROJECT_ROOT just needs to
# resolve to a writable path — config.py only `.resolve()`s it, doesn't
# require it to exist until a real fetch happens (which we don't expect
# inside this container).
ENV SPEC_SOURCE=markdown_local \
    SPEC_PROJECT_ROOT=/tmp/spec-project \
    PYTHONUNBUFFERED=1

WORKDIR /tmp/spec-project
ENTRYPOINT ["python", "-m", "mk_spec_master.server"]

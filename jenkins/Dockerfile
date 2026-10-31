# Jenkins with the Docker CLI installed inside it, so pipeline steps can run
# `docker build` / `docker push` by talking to the Docker socket we mount in from
# your laptop (Docker-outside-of-Docker - Jenkins doesn't run its own Docker engine,
# it just borrows yours).
FROM jenkins/jenkins:lts

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release \
                          python3 python3-pip python3-venv \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Plugins the pipeline will need: Git/GitHub integration, the Docker Pipeline DSL
# (the `docker.build(...)` / `docker.withRegistry(...)` steps), and Blue Ocean for a
# nicer pipeline view.
RUN jenkins-plugin-cli --plugins \
    "git:latest github:latest workflow-aggregator:latest docker-workflow:latest blueocean:latest credentials-binding:latest"

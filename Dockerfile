FROM docker:20.10 as docker
FROM python:3.12.7-bookworm

RUN useradd -u 1000 developper \
  && apt-get update -qq && apt-get install -qq --no-install-recommends \
    curl awscli unzip wget git vim

RUN groupadd -g 999 docker && usermod -aG docker developper

# Docker binary copy
COPY --from=docker /usr/local/bin/docker /usr/local/bin/

RUN pip install --upgrade pip && pip install aws-sam-cli

COPY --chown=developper:developper . /home/developper/app
WORKDIR /home/developper/app
RUN chown -R developper:developper /home/developper/app
USER developper

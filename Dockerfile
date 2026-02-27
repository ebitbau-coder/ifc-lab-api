FROM mambaorg/micromamba:1.5.8

COPY --chown=$MAMBA_USER:$MAMBA_USER env.yml /tmp/env.yml
RUN micromamba install -y -n base -f /tmp/env.yml && micromamba clean -a -y

WORKDIR /app
COPY --chown=$MAMBA_USER:$MAMBA_USER main.py /app/main.py

ENV PORT=8080
CMD ["micromamba", "run", "-n", "base", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

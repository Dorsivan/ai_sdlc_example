FROM registry.access.redhat.com/ubi9/python-311:latest

USER 0

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "huggingface_hub[cli]"

COPY download_models.py /app/download_models.py

RUN chmod 0755 /app/download_models.py && \
    chgrp -R 0 /app && \
    chmod -R g=u /app

ENV HOME=/tmp
ENV TMPDIR=/tmp
ENV HF_HOME=/tmp/.cache/huggingface
ENV HF_HUB_DISABLE_XET=1
ENV HF_HUB_DOWNLOAD_TIMEOUT=600
ENV HF_HUB_ETAG_TIMEOUT=120
ENV HF_HUB_VERBOSITY=info

USER 1001

ENTRYPOINT ["/app/download_models.py"]
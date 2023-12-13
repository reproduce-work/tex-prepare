FROM python:3.9-slim-buster

# Install essential tools and libraries
RUN apt-get update && apt-get install -y \
    wget \
    git \
    build-essential \ 
    && rm -rf /var/lib/apt/lists/*

RUN wget -O lowdown.tar.gz https://kristaps.bsd.lv/lowdown/snapshots/lowdown-1.1.0.tar.gz && \
    tar -xzf lowdown.tar.gz && \
    rm lowdown.tar.gz

# Make the configure script executable and run it
RUN \
    cd lowdown-1.1.0 &&\
    chmod +x configure &&\
    ./configure &&\
    make && \
    make regress && \
    make install install_libs

# Install from requirements.tfxt file
COPY --chown=${NB_UID}:${NB_GID} requirements.txt /tmp/
RUN pip install --quiet --no-cache-dir --requirement /tmp/requirements.txt

COPY run.py /run.py

WORKDIR /home


#docker run --rm -i -v $(pwd):/home -e REPROWORKDIR="reproduce" tex-prepare python build.py
#docker run --rm -i --net=none -v $(pwd):/home tex-compile sh -c "cd /home/reproduce/latex && xelatex compiled.tex"
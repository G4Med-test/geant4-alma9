# syntax=docker/dockerfile:1
# Inspired by carlomt/docker-geant4/almalinux9; one batch-validation image.
FROM almalinux:9 AS common
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Compilers remain in the final image: Apptainer %post builds each test.
RUN dnf install -y --setopt=install_weak_deps=False \
      gcc gcc-c++ make cmake expat-devel \
      python3.12 python3.12-pip tar gzip ca-certificates \
    && dnf clean all && rm -rf /var/cache/dnf

COPY requirements.txt /opt/g4med/requirements.txt
RUN python3.12 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --only-binary=:all: \
         -r /opt/g4med/requirements.txt

FROM common AS builder
ARG GEANT4_TAG
ARG GEANT4_COMMIT
ARG BUILD_JOBS=2
RUN [[ "$GEANT4_COMMIT" =~ ^[0-9a-f]{40}$ ]] \
    && mkdir -p /tmp/geant4/src \
    && curl -fLsS --retry 5 "https://codeload.github.com/Geant4/geant4/tar.gz/${GEANT4_COMMIT}" \
         -o /tmp/geant4.tar.gz \
    && tar -xzf /tmp/geant4.tar.gz -C /tmp/geant4/src --strip-components=1 \
    && cmake -S /tmp/geant4/src -B /tmp/geant4/build \
         -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/geant4 \
         -DGEANT4_INSTALL_DATA=OFF -DGEANT4_INSTALL_DATADIR=/g4data \
         -DGEANT4_BUILD_MULTITHREADED=ON -DGEANT4_BUILD_TLS_MODEL=global-dynamic \
         -DGEANT4_USE_SYSTEM_EXPAT=ON -DGEANT4_USE_GDML=OFF \
         -DGEANT4_USE_QT=OFF -DGEANT4_USE_OPENGL_X11=OFF \
         -DGEANT4_INSTALL_EXAMPLES=OFF \
    && cmake --build /tmp/geant4/build --parallel "$BUILD_JOBS" \
    && cmake --install /tmp/geant4/build --strip

FROM common AS final
ARG GEANT4_TAG
ARG GEANT4_COMMIT
ARG SOURCE_REVISION=unknown
LABEL org.opencontainers.image.title="G4Med Geant4 AlmaLinux 9" \
      org.opencontainers.image.description="Geant4 batch validation build environment with Python and uproot" \
      org.opencontainers.image.source="https://github.com/G4Med-test/geant4-alma9" \
      org.opencontainers.image.version="${GEANT4_TAG}" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.g4med.geant4.commit="${GEANT4_COMMIT}"
COPY --from=builder /opt/geant4/ /opt/geant4/
ENV PATH="/opt/venv/bin:/opt/geant4/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LD_LIBRARY_PATH="/opt/geant4/lib64:/opt/geant4/lib" \
    CMAKE_PREFIX_PATH="/opt/geant4" \
    G4INSTALL="/opt/geant4" \
    GEANT4_DATA_DIR="/g4data" \
    G4DATA_DIR="/g4data" \
    CC="/usr/bin/gcc" CXX="/usr/bin/g++" \
    LANG="C.UTF-8" PYTHONDONTWRITEBYTECODE="1"
RUN mkdir -p /g4data /workspace && chmod 1777 /g4data /workspace \
    && ln -s /g4data /opt/geant4/data \
    && geant4-config --version \
    && python3 -c 'import uproot, numpy; import importlib.util; assert importlib.util.find_spec("ROOT") is None'
WORKDIR /workspace
CMD ["bash"]

FROM ubuntu:focal

ENV GPG_KEY="09AEA2BAD52882A1AF9D6042F218DB829A9905B5"
ENV DEBFULLNAME="Egor Tensin"
ENV DEBEMAIL="egor@tensin.name"

ARG UID=1000
ARG GID=1000

RUN if ! id -n -g "$GID" ; then \
        groupadd -g "$GID" builder ; \
    fi

RUN if ! id -n -u "$UID" ; then \
        useradd -u "$UID" -g "$GID" --shell /bin/bash --create-home builder && \
        passwd -d builder ; \
    fi

RUN apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y --no-install-recommends \
        dirmngr \
        gpg \
        gpg-agent \
        git \
        make \
        sudo

# I'd prefer to run everything as root, but some bright person decided to
# hardcode sudo usage in git-pbuilder (https://manpages.org/git-pbuilder):
#
#     > In this case, it calls cowbuilder (or the configured builder as described above) _using sudo_
#
RUN echo 'ALL ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers

COPY ["prelude.mk", "/"]
COPY ["debian/Makefile", "/deps/"]
RUN make -C /deps deps

USER "$UID:$GID"

RUN git config --global user.name "$DEBFULLNAME" && \
    git config --global user.email "$DEBEMAIL"

ENV GNUPGHOME=/tmp/gnupg
RUN mkdir -p -- "$GNUPGHOME" && \
    chmod 0700 "$GNUPGHOME"

RUN gpg --keyserver hkp://keyserver.ubuntu.com/ --recv-keys "0x$GPG_KEY" && \
    echo "$GPG_KEY:6:" | gpg --import-ownertrust

COPY [".", "/app"]
WORKDIR /app/debian

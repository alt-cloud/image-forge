#!/bin/sh -eu

# Use bash to debug startup errors
if [ "${1-}" = bash ]; then
    exec bash
fi

if [ ! -f custom/conf/app.ini ]; then
    mkdir -p custom/conf
    cp /etc/gitea/app.ini -t custom/conf
fi

start_sshd() {
    # Store openssh config and keys in openssh directory to use them if
    # container recreats
    if [ -d openssh ]; then
        cp -a openssh/* /etc/openssh/
    else
        cp -a /etc/openssh -T openssh
    fi

    # Ensure keys created and saved to openssh directory
    /usr/bin/ssh-keygen -A
    cp -a /etc/openssh/* -t openssh

    /usr/sbin/sshd
}

start_sshd

chmod 0700 .
chown gitea:gitea . -R

exec gosu gitea /usr/bin/gitea web

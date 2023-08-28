dockerfiles-alt-systemd
========================

ALT dockerfile for systemd.

Copy Dockerfile somewhere and build the image:
`$ docker build --rm -t <username>/systemd .`

And launch the systemd container:
`docker run -d --name systemd --tmpfs /tmp --tmpfs /run --tmpfs /run/lock -v /sys/fs/cgroup:/sys/fs/cgroup:ro <username>/systemd`
`docker exec -it systemd bash`

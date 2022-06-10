dockerfiles-alt-etcd
=========================

ALT dockerfile for etcd.

Copy Dockerfile somewhere and build the image:
`$ docker build --rm -t <username>/etcd.`

And launch the etcd container:
`docker run -d -v <etcd data dir>:/data <username>/etcd`

If etcdclt watnted it could be run via:
`docker run --entrypoint etcdctl <username>/etcd`

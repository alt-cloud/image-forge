dockerfiles-alt-devel
======================

ALT dockerfile for developers.

DO NOT USE THIS IN PRODUCTION!

This image is only for devel or testing purposes. It contains packages that
usually need for debugging or testing something.

Copy Dockerfile somewhere and build the image:
`$ docker build --rm -t <username>/devel .`

And launch the devel container:
`docker run -it  <username>/devel`

dockerfiles-alt-unit
======================

ALT dockerfile for unit.

Copy Dockerfile somewhere and build the image:
`$ docker build --rm -t <username>/unit .`

And launch the unit container:
`docker run -it -p 80:80 <username>/unit`

It could be test via:
`curl localhost:80`

dockerfiles-alt-apache2
========================

ALT dockerfile for apache2.

Copy Dockerfile somewhere and build the image:
`$ docker build --rm -t <username>/apache2 .`

And launch the apache2 container:
`docker run -p 80:80 <username>/apache2`

It could be test via:
`curl localhost:80`

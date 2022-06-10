dockerfiles-alt-nginx
======================

ALT dockerfile for nginx.

Copy Dockerfile somewhere and build the image:
`$ docker build --rm -t <username>/nginx .`

And launch the nginx container:
`docker run -it -p 80:80 <username>/nginx`

It could be test via:
`curl localhost:80`

dockerfiles-alt-gitea
======================

ALT dockerfile for gitea.

Copy Dockerfile somewhere and build the image:
`$ docker build --rm -t <username>/gitea .`

And launch the gitea container:
`docker run -d -p 80:3000 -p 2222:22 -v <gitea_path>:/var/lib/gitea <username>/gitea`

## Configuration

After mounting gitea_path would contain all variable gitea data. Gitea
parameters could be customized via files in gitea_path.

Main configuration paths (relative to gitea_path):
* config -> custom/conf/app.ini;
* https certificates -> custom/https/;
* mail certificates -> custom/mailer/;
* openssh server configuration and keys -> openssh/;
* sqlite3 database -> data/gitea.db.

#!/bin/sh -eu

# Use bash to debug startup errors
if [ "${1-}" = bash ]; then
    exec bash
fi

configure_unit() {
    cat <<'EOF' > config.json
    {
        "listeners": {
            "*:80": {
                "pass": "routes"
            }
        },
        "routes": [
            {
                "action": {
                    "share": "/srv/www/html$uri",
                    "chroot": "/srv/www/html"
                }
            }
        ]
    }
EOF
    mkdir -p /srv/www/html
    echo '<html><body><h1>It works!</h1></body></html>' >  /srv/www/html/index.html

    while ! curl --unix-socket /var/run/unit/control.sock http://localhost; do
        sleep 0.1
    done

    curl -f -X PUT --data-binary @config.json \
        --unix-socket /var/run/unit/control.sock \
        http://localhost/config
}

configure_unit &

unitd --no-daemon

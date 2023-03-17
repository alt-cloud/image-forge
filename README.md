# image-forge

## alt images
To build `alt` images, run:
```
./build.py -o alt
```

## k8s images
To build `k8s` images for branch `p10` and push to repository `test_k8s`, run:
```
./build.py -o k8s -b p10 --overwrite-organization test_k8s --tasks tasks.json --tags tags.json
```

## distroless-images
### create
To create distroless image copy one of existing `org/alt/distroless-*` images.
Or create directory and copy `distroless-example.toml` to it, rename file to
`distroless.toml` and edit.

### build
For example if created image alt/distroless-false and you want to push to
the organization `<ORGANIZATION>`, run:
```
./build.py -i alt/distroless-false --overwrite-organization <ORGANIZATION>
```
If you push to the users repository, then organiztion is your username.

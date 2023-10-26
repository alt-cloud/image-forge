# image-forge

## alt images
To build `alt` images, run:
```bash
./build.py -o alt
```

## k8s images
To build `k8s` images for branch `p10` and push to repository `test_k8s`, run:
```bash
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
```bash
./build.py -i alt/distroless-false --overwrite-organization <ORGANIZATION>
```
If you push to the users repository, then organiztion is your username.

## Dependencies
On x86_64 machine using p10 branch you need:
- `python3-module-tomli`
- `qemu-user-static-binfmt-aarch64` to build for arm64 architecture
- `qemu-user-static-binfmt-arm` to build for arm architecture
- `qemu-user-static-binfmt-ppc` to build for ppc64le architecture

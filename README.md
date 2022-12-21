docker-derivatives
==================

To build `alt` images, run:

```
./build.py -o alt --podman
```

To build `k8s` images for branch `p10` and push to repository `test_k8s`, run:

```
./build.py -o k8s -b p10 --overwrite-organization test_k8s --tasks tasks.json --tags tags.json --podman
```

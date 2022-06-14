#!/usr/bin/python3

import argparse
import os
import re
import subprocess
from graphlib import TopologicalSorter
from pathlib import Path

from jinja2 import Template


IMAGES_DIR = Path("images")


class DockerBuilder:
    def make_from_re(self):
        registry = r"(?P<registry>[\w.:]+)"
        organization = r"(?P<organization>\w+)"
        name = r"(?P<name>\w+)"
        tag = r"(?P<tag>[\w.]+)"
        return f"^FROM (:?{registry}/)?(:?{organization}/)?{name}(:?:{tag})?$"

    def __init__(self, registry, organization, latest, dry_run):
        self.from_re = re.compile(self.make_from_re())
        self.images_dir = IMAGES_DIR
        self.registry = registry
        self.organization = organization
        self.latest = latest
        self.dry_run = dry_run

    def forall_images(consume_result):
        def forall_images_decorator(f):
            def wrapped(self, *args, **kwargs):
                for image in self.images_dir.iterdir():
                    local_kwargs = {
                        "image": image,
                        "dockerfile": image / "Dockerfile",
                        "dockerfile_template": image / "Dockerfile.template",
                    }
                    new_kwargs = kwargs | local_kwargs
                    yield f(self, *args, **new_kwargs)

            def consumer(*args, **kwargs):
                for _ in wrapped(*args, **kwargs):
                    pass

            if consume_result:
                return consumer
            else:
                return wrapped

        return forall_images_decorator

    @forall_images(consume_result=True)
    def remove_dockerfiles(self, **kwargs):
        if kwargs["dockerfile"].exists():
            kwargs["dockerfile"].unlink()

    @forall_images(consume_result=True)
    def render_dockerfiles(self, branch, **kwargs):
        if kwargs["dockerfile_template"].exists():
            if self.registry:
                registry = self.registry.rstrip("/") + "/"
                alt_image = "alt/alt"
            else:
                registry = ""
                alt_image = "alt"
            rendered = Template(kwargs["dockerfile_template"].read_text()).render(
                alt_image=alt_image,
                branch=branch,
                organization=self.organization,
                registry=registry,
            )
            kwargs["dockerfile"].write_text(rendered + "\n")

    @forall_images(consume_result=False)
    def get_requires(self, **kwargs):
        requires = set()

        for line in kwargs["dockerfile"].read_text().splitlines():
            if match := re.match(self.from_re, line):
                from_image = match.groupdict()
                if from_image["organization"] == self.organization:
                    requires.add(from_image["name"])

        return (kwargs["image"].name, requires)

    def get_build_order(self):
        requires = {}
        for image, image_requires in self.get_requires():
            requires[image] = image_requires
        ts = TopologicalSorter(requires)
        return ts.static_order()

    def render_full_tag(self, image, tag):
        if self.registry:
            registry = self.registry.rstrip("/") + "/"
        else:
            registry = ""
        if tag:
            tag = f":{tag}"
        return f"{registry}{self.organization}/{image}{tag}"

    def run(self, cmd, *args, **kwargs):
        if self.dry_run:
            pre_cmd = ["echo"]
        else:
            pre_cmd = []
        subprocess.run(pre_cmd + cmd, *args, **kwargs)

    def build(self, image, arches, tag):
        new_env = os.environ | {"DOCKER_BUILDKIT": "1"}

        platforms = ",".join([f"linux/{a}" for a in arches])
        full_name = self.render_full_tag(image, tag)
        if tag == self.latest:
            lates_name = self.render_full_tag(image, "latest")
            names = f"{full_name},{lates_name}"
        else:
            names = full_name

        cmd = [
            "buildctl",
            "build",
            "--frontend=dockerfile.v0",
            "--local",
            "context=.",
            "--local",
            "dockerfile=.",
            "--opt",
            f"platform={platforms}",
            "--output",
            f'type=image,"name={names}",push=true',
        ]
        self.run(
            cmd,
            cwd=self.images_dir / image,
            env=new_env,
        )


def parse_args():
    stages = ["build", "remove_dockerfiles", "render_dockerfiles"]
    arches = ["amd64", "386", "arm64", "arm", "ppc64le"]
    branches = ["p9", "p10", "sisyphus"]
    images = os.listdir(IMAGES_DIR)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-r",
        "--registry",
        default="registry.altlinux.org",
    )
    parser.add_argument(
        "-o",
        "--organization",
        default="alt",
    )
    parser.add_argument(
        "-l",
        "--latest",
        default="p10",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print instead of running docker commands",
    )
    parser.add_argument(
        "-i",
        "--images",
        nargs="+",
        default=images,
        choices=images,
        help="list of branches",
    )
    parser.add_argument(
        "--skip-images",
        nargs="+",
        default=[],
        choices=images,
        help="list of skipping images",
    )
    parser.add_argument(
        "-a",
        "--arches",
        nargs="+",
        default=arches,
        choices=arches,
        help="list of arches",
    )
    parser.add_argument(
        "--skip-arches",
        nargs="+",
        default=[],
        choices=arches,
        help="list of skipping arches",
    )
    parser.add_argument(
        "-b",
        "--branches",
        nargs="+",
        default=branches,
        choices=branches,
        help="list of branches",
    )
    parser.add_argument(
        "--skip-branches",
        nargs="+",
        default=[],
        choices=branches,
        help="list of skipping branches",
    )
    parser.add_argument(
        "--stages",
        nargs="+",
        default=stages,
        choices=stages,
        help="list of stages",
    )
    parser.add_argument(
        "--skip-stages",
        nargs="+",
        default=[],
        choices=stages,
        help="list of skipping stages",
    )
    args = parser.parse_args()

    args.stages = set(args.stages) - set(args.skip_stages)
    args.branches = set(args.branches) - set(args.skip_branches)
    args.images = set(args.images) - set(args.skip_images)

    return args


def main():
    args = parse_args()
    for branch in args.branches:
        db = DockerBuilder(args.registry, args.organization, args.latest, args.dry_run)
        if "remove_dockerfiles" in args.stages:
            db.remove_dockerfiles()
        if "render_dockerfiles" in args.stages:
            db.render_dockerfiles(branch)
        if "build" in args.stages:
            for image in db.get_build_order():
                if image not in args.images:
                    continue

                if "build" in args.stages:
                    db.build(image, args.arches, branch)


if __name__ == "__main__":
    main()

# vim: colorcolumn=89

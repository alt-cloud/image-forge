#!/usr/bin/python3

import argparse
import functools
import json
import re
import subprocess
import textwrap
from graphlib import TopologicalSorter
from pathlib import Path

import tomli
from jinja2 import Template


ORG_DIR = Path("org")


class Image:
    def __init__(self, canonical_name):
        self.canonical_name = canonical_name
        self.path = ORG_DIR / canonical_name
        self.base_name = re.sub("^[^/]+/", "", canonical_name)


class Tasks:
    def __init__(self, tasks):
        if tasks is None:
            self._tasks = None
        else:
            self._tasks = json.loads(Path(tasks).read_text())

    def get(self, branch, image: Image):
        if self._tasks is None:
            return []
        else:
            if branch_tasks := self._tasks.get(branch):
                return [
                    n
                    for n, i in branch_tasks.items()
                    if image.canonical_name in i or len(i) == 0
                ]


class Tags:
    def __init__(self, tags_file, latest):
        if tags_file is None:
            self._tags = None
        else:
            tags_file = Path(tags_file)
            self._tags = json.loads(tags_file.read_text())
        self._latest = latest

    def tags(self, branch, image: Image):
        if self._tags is None:
            tags = [branch]
        else:
            tags = self._tags[image.canonical_name][branch]
        if branch == self._latest:
            tags.append("latest")
        return tags


class Distroless:
    def __init__(self, distrolessfile, renderer):
        dd = tomli.loads(distrolessfile.read_text())

        self.raw_from = dd["from"]
        self.from_ = renderer(dd["from"])

        self.file_lists = dd.get("file-lists", [])
        self.files = dd.get("files", [])
        self.packages = dd.get("packages", [])
        self.exclude_regexes = dd.get("exclude-regexes", [])

        self.builder_install_packages = dd.get("builder-install-packages")

        self.timezone = dd.get("timezone")

        self.copy = dd.get("copy", {})

        self.config_options = []
        for option in ["cmd", "entrypoint", "user"]:
            if value := dd.get(option):
                self.config_options.append(f"--{option}={value}")
        if value := dd.get("workdir"):
            self.config_options.append(f"--workingdir={value}")
        elif value := dd.get("workingdir"):
            self.config_options.append(f"--workingdir={value}")


class DockerBuilder:
    def make_image_re(self):
        registry = r"(?P<registry>[\w.:]+)"
        organization = r"(?P<organization>\w+)"
        name = r"(?P<name>[-.\w]+)"
        tag = r"(?P<tag>[\w.]+)"
        return rf"(:?{registry}/)?(:?{organization}/)?{name}(:?:{tag})?"

    def make_dockerfile_from_re(self):
        image_re = self.make_image_re()
        return rf"^\s*FROM\s+{image_re}$"

    def __init__(
        self,
        registry,
        branch,
        organization,
        overwrite_organization,
        latest,
        dry_run,
        images_info,
        tasks: Tasks,
        tags: Tags,
    ):
        self.image_re = re.compile(self.make_image_re())
        self.dockerfile_from_re = re.compile(self.make_dockerfile_from_re())
        self.org_dir = ORG_DIR
        self.images_dir = ORG_DIR / organization
        self.registry = registry
        self.branch = branch
        self.organization = organization
        if overwrite_organization:
            self.overwrite_organization = overwrite_organization
        else:
            self.overwrite_organization = organization
        self.latest = latest
        self.dry_run = dry_run
        self.images_info = images_info
        self.tasks = tasks
        self.tags = tags
        self.distrolesses = {}

    def forall_images(consume_result):
        def forall_images_decorator(f):
            def wrapped(self, *args, **kwargs):
                for image_path in self.images_dir.iterdir():
                    image = Image("/".join(image_path.parts[1:]))
                    local_kwargs = {
                        "image": image,
                        "dockerfile": image_path / "Dockerfile",
                        "dockerfile_template": image_path / "Dockerfile.template",
                        "distrolessfile": image_path / "distroless.toml",
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

    def render_template(
        self, template: str, organization: str, install_pakages=None
    ) -> str:
        if self.registry:
            registry = self.registry.rstrip("/") + "/"
            alt_image = "alt/alt"
        else:
            registry = ""
            alt_image = "alt"
        rendered = Template(template).render(
            alt_image=alt_image,
            branch=self.branch,
            install_pakages=install_pakages,
            organization=organization,
            registry=registry,
        )

        return rendered

    @forall_images(consume_result=True)
    def render_dockerfiles(self, **kwargs):
        def install_pakages(*names):
            tasks = self.tasks.get(self.branch, kwargs["image"].canonical_name)
            linux32 = '$([ "$(rpm --eval %_host_cpu)" = i586 ] && echo linux32)'
            if tasks:
                apt_repo = "\\\n    apt-get install apt-repo -y && \\"
                for task in tasks:
                    apt_repo += f"\n    {linux32} apt-repo add {task} && \\"
                apt_repo += "\n    apt-get update && \\"
            else:
                apt_repo = "\\"
            update_command = f"""RUN apt-get update && {apt_repo}"""
            install_command = f"""
            {linux32} apt-get install -y {' '.join(names)} && \\
            rm -f /var/cache/apt/archives/*.rpm \\
                  /var/cache/apt/*.bin \\
                  /var/lib/apt/lists/*.*
            """
            install_command = textwrap.dedent(install_command).rstrip("\n")
            install_command = textwrap.indent(install_command, " " * 4)
            return update_command + install_command

        dockerfile_template = kwargs["dockerfile_template"]
        if dockerfile_template.exists():
            rendered = self.render_template(
                dockerfile_template.read_text(),
                self.overwrite_organization,
                install_pakages,
            )
            kwargs["dockerfile"].write_text(rendered + "\n")

    @forall_images(consume_result=True)
    def load_distrolesses(self, **kwargs):
        renderer = functools.partial(
            self.render_template,
            organization=self.overwrite_organization,
        )
        distrolessfile = kwargs["distrolessfile"]
        canonical_name = "/".join(distrolessfile.parts[-3:-1])
        if distrolessfile.exists():
            self.distrolesses[canonical_name] = Distroless(distrolessfile, renderer)

    @forall_images(consume_result=False)
    def get_requires(self, **kwargs):
        requires = set()
        dockerfile_template = kwargs["dockerfile_template"]
        distrolessfile = kwargs["distrolessfile"]
        canonical_name = kwargs["image"].canonical_name

        if dockerfile_template.exists():
            for line in dockerfile_template.read_text().splitlines():
                if not re.match(r"\s*FROM", line):
                    continue
                line = self.render_template(line, self.organization)
                if match := re.match(self.dockerfile_from_re, line):
                    from_image = match.groupdict()
                    if from_image["name"] != "scratch":
                        requires.add(
                            f"{from_image['organization']}/{from_image['name']}"
                        )
        elif distrolessfile.exists():
            requires.add("alt/distroless-builder")
            raw_from = self.distrolesses[canonical_name].raw_from
            from_ = self.render_template(raw_from, self.organization)
            if match := re.match(self.image_re, from_):
                from_image = match.groupdict()
                if from_image["name"] != "scratch":
                    requires.add(f"{from_image['organization']}/{from_image['name']}")

        return (canonical_name, requires)

    def get_build_order(self):
        requires = {}
        for canonical_name, image_requires in self.get_requires():
            requires[canonical_name] = image_requires
        ts = TopologicalSorter(requires)
        return (Image(i) for i in ts.static_order())

    def render_full_tag(self, image: Image, tag: str):
        if self.registry:
            registry = self.registry.rstrip("/") + "/"
        else:
            registry = ""
        if tag:
            tag = f":{tag}"
        return f"{registry}{self.overwrite_organization}/{image.base_name}{tag}"

    def run(self, cmd, *args, **kwargs):
        if "check" not in kwargs:
            kwargs["check"] = True
        if self.dry_run:
            pre_cmd = ["echo"]
        else:
            pre_cmd = []
        subprocess.run(pre_cmd + cmd, *args, **kwargs)

    def distroless_build(self, image: Image, arches):
        def distroless_build_arch(arch, manifest):
            distroless_builder = self.render_full_tag(
                Image("alt/distroless-builder"), self.branch
            )
            distroless = self.distrolesses[image.canonical_name]
            builder = f"distroless-builder-{arch}"
            new = f"distroless-new-{arch}"
            run = functools.partial(self.run, cwd=image.path)
            run(
                ["buildah", "rm", builder, new],
                check=False,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
            )
            run(
                [
                    "buildah",
                    "from",
                    "--arch",
                    arch,
                    "--name",
                    builder,
                    distroless_builder,
                ]
            )
            run(["buildah", "from", "--arch", arch, "--name", new, distroless.from_])

            if packages := distroless.builder_install_packages:
                run(["buildah", "run", builder, "apt-get", "update"])
                run(
                    ["buildah", "run", builder, "apt-get", "reinstall", "-y"] + packages
                )

            if timezone := distroless.timezone:
                run(
                    [
                        "buildah",
                        "run",
                        builder,
                        "ln",
                        "-s",
                        f"/usr/share/zoneinfo/{timezone}",
                        "/etc/localtime",
                    ]
                )

            files_options = []
            file_lists_options = []
            packages_options = []
            if distroless.files:
                files_options = ["-f"] + distroless.files
            if file_lists := distroless.file_lists:
                file_lists_options = ["-l"]
                file_lists_options.extend([f"file-lists/{f}" for f in file_lists])
                for file_list in file_lists:
                    run(
                        [
                            "buildah",
                            "copy",
                            builder,
                            f"./{file_list}",
                            f"file-lists/{file_list}",
                        ]
                    )
            if distroless.packages:
                packages_options = ["-p"] + distroless.packages

            run(
                [
                    "buildah",
                    "run",
                    builder,
                    "./distroless-builder.py",
                    "add",
                    "--clean",
                ]
                + files_options
                + file_lists_options
                + packages_options
            )

            exclude_regexes_options = []
            if distroless.exclude_regexes:
                exclude_regexes_options = ["-r"] + distroless.exclude_regexes
            run(
                [
                    "buildah",
                    "run",
                    builder,
                    "./distroless-builder.py",
                    "tar",
                ]
                + exclude_regexes_options
            )

            run(
                [
                    "buildah",
                    "add",
                    "--from",
                    builder,
                    new,
                    "/usr/src/distroless/distroless.tar",
                    "/",
                ]
            )

            for local_file, image_file in distroless.copy.items():
                run(
                    [
                        "buildah",
                        "copy",
                        new,
                        f"./{local_file}",
                        image_file,
                    ]
                )

            run(["buildah", "config"] + distroless.config_options + [new])

            run(["buildah", "commit", "--rm", "--manifest", manifest, new])
            run(
                ["buildah", "rm", builder],
                check=False,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
            )

        if self.images_info.skip_branch(image.canonical_name, self.branch):
            return

        build_arches = set(arches) - set(
            self.images_info.skip_arches(image.canonical_name)
        )
        tags = self.tags.tags(self.branch, image.canonical_name)
        manifest = self.render_full_tag(image, tags[0])

        msg = "Building image {} for {} arches".format(
            manifest,
            arches,
        )
        print(msg)

        rm_image_cmd = [
            "podman",
            "image",
            "rm",
            "--force",
            manifest,
        ]
        self.run(
            rm_image_cmd,
            check=False,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )
        rm_manifest_cmd = [
            "podman",
            "manifest",
            "rm",
            manifest,
        ]
        self.run(
            rm_manifest_cmd,
            check=False,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )

        for arch in build_arches:
            distroless_build_arch(arch, manifest)

        for tag in tags[1:]:
            other_manifest = self.render_full_tag(image, tag)
            tag_cmd = ["podman", "tag", manifest, other_manifest]
            self.run(tag_cmd)

    def podman_build(self, image: Image, arches):
        if self.images_info.skip_branch(image.canonical_name, self.branch):
            return

        build_arches = set(arches) - set(
            self.images_info.skip_arches(image.canonical_name)
        )
        platforms = ",".join([f"linux/{a}" for a in build_arches])
        tags = self.tags.tags(self.branch, image.canonical_name)
        manifest = self.render_full_tag(image, tags[0])

        msg = "Building image {} for {} arches".format(
            manifest,
            arches,
        )
        print(msg)

        rm_image_cmd = [
            "podman",
            "image",
            "rm",
            "--force",
            manifest,
        ]
        self.run(
            rm_image_cmd,
            check=False,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )
        rm_manifest_cmd = [
            "podman",
            "manifest",
            "rm",
            manifest,
        ]
        self.run(
            rm_manifest_cmd,
            check=False,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )
        build_cmd = [
            "podman",
            "build",
            "--rm",
            "--force-rm",
            f"--manifest={manifest}",
            f"--platform={platforms}",
            ".",
        ]
        self.run(build_cmd, cwd=image.path)

        for tag in tags[1:]:
            other_manifest = self.render_full_tag(image, tag)
            tag_cmd = ["podman", "tag", manifest, other_manifest]
            self.run(tag_cmd)

    def podman_push(self, image: Image, sign=None):
        if self.images_info.skip_branch(image.canonical_name, self.branch):
            return

        tags = self.tags.tags(self.branch, image.canonical_name)
        manifests = [self.render_full_tag(image, t) for t in tags]

        for manifest in manifests:
            print(f"Push manifest {manifest}")
            cmd = [
                "podman",
                "manifest",
                "push",
                manifest,
                f"docker://{manifest}",
            ]

            if sign is not None:
                cmd.append(f"--sign-by={sign}")

            self.run(cmd)


class ImagesInfo:
    def __init__(self):
        info = {}
        images_info = Path("images-info.json")
        if images_info.exists():
            info = json.loads(images_info.read_text())

        self._info = info

    def skip_arch(self, canonical_name, arch):
        info = self._info.get(canonical_name, {})
        return arch in info.get("skip-arches", [])

    def skip_arches(self, canonical_name):
        info = self._info.get(canonical_name, {})
        return info.get("skip-arches", [])

    def skip_branch(self, canonical_name, branch):
        info = self._info.get(canonical_name, {})
        return branch in info.get("skip-branches", [])

    def skip_branches(self, canonical_name):
        info = self._info.get(canonical_name, {})
        return info.get("skip-branches", [])


def parse_args():
    stages = ["build", "remove_dockerfiles", "render_dockerfiles", "push"]
    arches = ["amd64", "386", "arm64", "arm", "ppc64le"]
    branches = ["p9", "p10", "sisyphus"]
    organizations = list(ORG_DIR.iterdir())
    images = [f"{o.name}/{i.name}" for o in organizations for i in o.iterdir()]
    organizations = [o.name for o in organizations]

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    images_group = parser.add_mutually_exclusive_group(required=True)
    images_group.add_argument(
        "-i",
        "--images",
        nargs="+",
        default=images,
        choices=images,
        help="list of branches",
    )
    images_group.add_argument(
        "-o",
        "--organizations",
        nargs="+",
        default=organizations,
        choices=organizations,
        help="build all images from these organizations",
    )
    parser.add_argument(
        "-r",
        "--registry",
        default="registry.altlinux.org",
    )
    parser.add_argument(
        "--overwrite-organization",
    )
    parser.add_argument(
        "-l",
        "--latest",
        default="p10",
    )
    parser.add_argument(
        "--tasks",
        type=Tasks,
        default=Tasks(None),
    )
    parser.add_argument(
        "--tags",
        help="use tags from TAGS file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print instead of running docker commands",
    )
    parser.add_argument(
        "--sign",
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
    arches = args.arches
    images_info = ImagesInfo()
    tags = Tags(args.tags, args.latest)
    for organization in args.organizations:
        for branch in args.branches:
            db = DockerBuilder(
                args.registry,
                branch,
                organization,
                args.overwrite_organization,
                args.latest,
                args.dry_run,
                images_info,
                args.tasks,
                tags,
            )
            if "remove_dockerfiles" in args.stages:
                db.remove_dockerfiles()
            if "render_dockerfiles" in args.stages:
                db.render_dockerfiles()
            db.load_distrolesses()
            for image in db.get_build_order():
                if image.canonical_name not in args.images:
                    continue

                if "build" in args.stages:
                    if image.canonical_name in db.distrolesses:
                        db.distroless_build(image, arches)
                    else:
                        db.podman_build(image, arches)

                if "push" in args.stages:
                    db.podman_push(image, args.sign)


if __name__ == "__main__":
    main()

# vim: colorcolumn=89

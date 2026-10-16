"""Create an offline Docker runtime from the pinned hamio Nix development shell."""

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def build(baseline: Path, context: Path, tag: str) -> dict:
    context.mkdir(parents=True, exist_ok=False)
    nix = "/nix/var/nix/profiles/default/bin/nix"
    result = subprocess.run(
        [nix, "develop", "--no-write-lock-file", str(baseline), "--command",
         "printenv", "PATH", "HAMIO_BUN_RUNTIME"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    paths = [p for p in result[0].split(":") if p.startswith("/nix/store/")]
    runtime = result[1]
    roots = sorted({"/".join(p.split("/")[:4]) for p in [*paths, runtime]})
    closure = subprocess.run(
        ["/nix/var/nix/profiles/default/bin/nix-store", "--query", "--requisites", *roots],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    root = context / "root"
    root.mkdir()
    for path in sorted(set(closure)):
        destination = root / path.lstrip("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if Path(path).is_dir():
            shutil.copytree(path, destination, symlinks=True)
        else:
            shutil.copy2(path, destination, follow_symlinks=False)
    # The embedded upstream runtime is deliberately unpatched and uses the host loader.
    executables = [runtime, str(baseline / "node_modules/@biomejs/cli-linux-x64/biome")]
    libraries = "\n".join(subprocess.run(["ldd", executable], check=True, capture_output=True, text=True).stdout for executable in executables)
    host_libraries = sorted(set(re.findall(r"(/[^\s()]+)", libraries)))
    for library in host_libraries:
        destination = root / library.lstrip("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library, destination)
    bash = next(p + "/bash" for p in paths if "-bash-" in p)
    coreutils = next(p for p in paths if "-coreutils-" in p)
    for name, destination in (("bin/sh", bash), ("bin/bash", bash), ("usr/bin/env", coreutils + "/env")):
        link = root / name
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(destination)
    # Frozen installer tests intentionally use a clean /usr/bin:/bin PATH.
    tool_bins = [*paths, *(path + "/bin" for path in closure if "-gzip-" in path)]
    for tool_bin in tool_bins:
        for executable in Path(tool_bin).glob("*"):
            alias = root / "usr/bin" / executable.name
            if executable.is_file() and not alias.is_symlink() and not alias.exists():
                alias.symlink_to(executable)
    (root / "etc").mkdir()
    (root / "etc/passwd").write_text("nobody:x:65534:65534:nobody:/work/home:/bin/sh\n")
    (root / "etc/group").write_text("nogroup:x:65534:\n")
    (root / "tmp").mkdir(mode=0o777)
    dockerfile = (
        "FROM scratch\nCOPY root/ /\n"
        f"ENV PATH={':'.join(paths)}:/bin:/usr/bin\n"
        f"ENV HAMIO_BUN_RUNTIME={runtime}\n"
        "ENV HAMIO_DEV_SHELL=1 HOME=/work/home TMPDIR=/work LANG=C.UTF-8\n"
    )
    (context / "Dockerfile").write_text(dockerfile)
    subprocess.run(["docker", "build", "--network=none", "-t", tag, str(context)], check=True)
    image = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", tag], check=True, capture_output=True, text=True).stdout.strip()
    manifest = {"image_id": image, "nix_roots": roots, "nix_closure": sorted(set(closure)), "host_libraries": host_libraries, "path": paths, "upstream_runtime": runtime}
    (context / "runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--tag", default="hamio-recover-grader:local")
    args = parser.parse_args()
    print(json.dumps(build(args.baseline.resolve(), args.context.resolve(), args.tag)))

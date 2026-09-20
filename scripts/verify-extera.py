import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

BASELINE = "db3b9891cb0b04ebb7d8c0e71ada3bcc669b910a"
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".ai/extera-verification")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("Verification output must be inside this checkout")
    output.mkdir(parents=True, exist_ok=True)
    records = []

    def run(command, cwd=ROOT):
        process = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        records.append(dict(command=command, cwd=str(cwd), exit_status=process.returncode,
                            stdout=process.stdout, stderr=process.stderr))
        return process

    baseline = run(["git", "ls-tree", "--name-only", BASELINE,
                    "Telegram/SourceFiles/extera", "Telegram/Resources/extera_runtime"])
    if baseline.returncode or baseline.stdout.strip():
        raise ValueError("Unexpected baseline feature state")
    modified = run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/extera", "-v"])
    changes = run(["git", "diff", "--name-only", BASELINE]).stdout.splitlines()
    untracked = run(["git", "ls-files", "--others", "--exclude-standard"]).stdout.splitlines()
    files = sorted(set(changes + untracked))
    fixture = output / "rollback-check"
    fixture.mkdir(exist_ok=True)
    manifest = dict(schema=1, baseline=BASELINE, files=[])
    for name in files:
        path = ROOT / name
        if not path.is_file() or name.startswith(".ai/"):
            continue
        content = path.read_bytes()
        previous = subprocess.run(["git", "show", BASELINE + ":" + name], cwd=ROOT, capture_output=True)
        baseline_hash = None
        if previous.returncode == 0:
            backup = output / "baseline" / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(previous.stdout)
            baseline_hash = hashlib.sha256(previous.stdout).hexdigest()
        target = fixture / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest["files"].append(dict(path=name, baseline_sha256=baseline_hash,
                                      modified_sha256=hashlib.sha256(content).hexdigest()))
    manifest_path = output / "rollback-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    rollback_results = []
    if powershell:
        common = [powershell, "-NoProfile", "-File", str(ROOT / "scripts/rollback-extera.ps1"),
                  "-Manifest", str(manifest_path), "-Root", str(fixture)]
        rollback_results = [run(common), run(common + ["-Apply"])]
    else:
        raise RuntimeError("PowerShell is required to verify the runnable rollback")
    for entry in manifest["files"]:
        restored = fixture / entry["path"]
        if entry["baseline_sha256"]:
            assert hashlib.sha256(restored.read_bytes()).hexdigest() == entry["baseline_sha256"]
        else:
            assert not restored.exists()
    patch = subprocess.run(["git", "diff", "--binary", BASELINE], cwd=ROOT, capture_output=True, check=True)
    (output / "extera.patch").write_bytes(patch.stdout)
    run(["git", "diff", "--check", BASELINE])
    result = dict(baseline=BASELINE, records=records,
                  python_tests_passed=modified.returncode == 0,
                  rollback_passed=all(p.returncode == 0 for p in rollback_results),
                  desktop_build="See GitHub Actions; Python tests do not verify the C++ GUI",
                  manifest=str(manifest_path), patch=str(output / "extera.patch"))
    (output / "verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=2))
    return 0 if result["python_tests_passed"] and result["rollback_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

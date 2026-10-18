#!/bin/sh
# Project-local installer; also works via: curl .../install.sh | sh -s -- ...
set -eu

INSTALLER_VERSION=0.3.1
# Public default; --repo and HARNESS_REPO can override it.
DEFAULT_REPO=ilovn/AI-Agents-Scripts
repo=${HARNESS_REPO:-$DEFAULT_REPO}
project=$PWD
version=$INSTALLER_VERSION
ref=
version_selected=false
ref_selected=false
mode=auto
tools=
dry_run=false
replace_modified=false
python=${HARNESS_PYTHON:-python3}

usage() {
    cat <<'USAGE'
AI Harness Kit installer

Usage:
  sh install.sh [options]
  curl -fsSL https://raw.githubusercontent.com/ilovn/AI-Agents-Scripts/v0.3.1/install.sh | sh

Options:
  --repo REPOSITORY     GitHub OWNER/REPO, HTTPS/SSH Git URL, or local Git path
                       Default: ilovn/AI-Agents-Scripts (or HARNESS_REPO)
  --version X.Y.Z       Fetch tag vX.Y.Z and verify the source version
                       Default: the version of this installer (0.3.1)
  --ref REF             Fetch a branch, tag or full commit instead of --version
  --project DIRECTORY  Target project (default: the caller's current directory)
  --tools LIST         Comma-separated: claude,codex,opencode,trae
                       Omit to install all on init, preserve selection on upgrade
  --mode MODE          auto (default), init, or upgrade
  --dry-run            Download/validate source and preview; do not write project
  --replace-modified   Explicitly replace conflicting managed content with backups
  --python EXECUTABLE  Python 3.10+ executable (or HARNESS_PYTHON)
  -h, --help           Show this help

Requires Python 3.10+ and Git. No sudo, pip, global CLI install or shell profile edits.
USAGE
}

fail() {
    printf 'ai-harness installer: %s\n' "$*" >&2
    exit 2
}

need_value() {
    [ "$#" -ge 2 ] && [ -n "$2" ] || fail "missing value for $1"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --repo) need_value "$@"; repo=$2; shift 2 ;;
        --version) need_value "$@"; version=${2#v}; version_selected=true; shift 2 ;;
        --ref) need_value "$@"; ref=$2; ref_selected=true; shift 2 ;;
        --project) need_value "$@"; project=$2; shift 2 ;;
        --tools) need_value "$@"; tools=$2; shift 2 ;;
        --mode) need_value "$@"; mode=$2; shift 2 ;;
        --python) need_value "$@"; python=$2; shift 2 ;;
        --dry-run) dry_run=true; shift ;;
        --replace-modified) replace_modified=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) fail "unknown option: $1" ;;
    esac
done

[ -n "$repo" ] || fail 'provide --repo OWNER/REPO (or set HARNESS_REPO)'
[ "$version_selected" = false ] || [ "$ref_selected" = false ] || fail '--version and --ref are mutually exclusive'
case "$mode" in auto|init|upgrade) ;; *) fail '--mode must be auto, init or upgrade' ;; esac
case "$tools" in ,*|*,|*,,*) fail '--tools requires a comma-separated list without empty items' ;; esac
remaining=$tools
while [ -n "$remaining" ]; do
    tool=${remaining%%,*}
    case "$tool" in claude|codex|opencode|trae) ;; *) fail "unsupported tool: $tool" ;; esac
    case "$remaining" in *,*) remaining=${remaining#*,} ;; *) remaining= ;; esac
done

command -v "$python" >/dev/null 2>&1 || fail "Python executable not found: $python"
"$python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10+ is required")'
command -v git >/dev/null 2>&1 || fail 'Git is required'
if [ "$ref_selected" = false ]; then
    "$python" -c 'import re, sys; sys.exit(0 if re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]) else "--version must be X.Y.Z or vX.Y.Z")' "$version"
    ref=v$version
else
    case "$ref" in -*|'') fail 'invalid Git ref' ;; esac
fi
case "$repo" in
    https://*|ssh://*|git@*|/*|./*|../*|file://*) repo_url=$repo ;;
    *)
        case "$repo" in *[!A-Za-z0-9._/-]*|-*|*..*) fail 'invalid OWNER/REPO; use a Git URL for other hosts' ;; esac
        owner=${repo%%/*}
        name=${repo#*/}
        [ "$owner" != "$repo" ] && [ -n "$owner" ] && [ -n "$name" ] || fail 'use OWNER/REPO or a Git URL'
        case "$name" in */*) fail 'use OWNER/REPO or a Git URL' ;; esac
        repo_url=https://github.com/${repo%.git}.git
        ;;
esac
# Resolve caller-relative paths before operating in a temporary checkout.
project=$("$python" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$project")
case "$repo_url" in
    /*|./*|../*) repo_url=$("$python" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$repo_url") ;;
esac

# Do not let Git credential prompts consume the remainder of a piped shell script.
GIT_TERMINAL_PROMPT=0
export GIT_TERMINAL_PROMPT
checkout_tmp=$(mktemp -d "${TMPDIR:-/tmp}/ai-harness-install.XXXXXX")
cleanup() { rm -rf -- "$checkout_tmp"; }
trap cleanup 0
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
source_dir=$checkout_tmp/source
printf 'Fetching %s at %s\n' "$repo_url" "$ref" >&2
git init -q "$source_dir" >&2
git -C "$source_dir" remote add origin "$repo_url"
git -C "$source_dir" fetch --quiet --depth=1 -- origin "$ref" </dev/null
git -C "$source_dir" -c advice.detachedHead=false checkout --quiet --detach FETCH_HEAD
commit=$(git -C "$source_dir" rev-parse HEAD)
[ -f "$source_dir/harness.py" ] && [ -d "$source_dir/harnesskit" ] || fail 'selected source is not an AI Harness Kit checkout'
actual_version=$("$python" "$source_dir/harness.py" --version)
"$python" -c 'import re, sys; value = sys.argv[1]; sys.exit(0 if re.fullmatch(r"\d+\.\d+\.\d+", value) and tuple(map(int, value.split("."))) >= (0, 3, 0) else "install.sh requires source kit 0.3.0+; install older kits from their checkout")' "$actual_version"
if [ "$ref_selected" = false ] && [ "$actual_version" != "$version" ]; then
    fail "tag/source version mismatch: requested $version, source reports $actual_version"
fi
source_json=$("$python" -c 'import json, sys; print(json.dumps(dict(zip(("repository", "ref", "commit"), sys.argv[1:]))))' "$repo_url" "$ref" "$commit")
if [ "$mode" = auto ]; then
    if [ -f "$project/.harness/manifest.json" ]; then mode=upgrade; else mode=init; fi
fi
set -- "$python" "$source_dir/harness.py" --project "$project" "$mode" --source "$source_json"
if [ -n "$tools" ]; then
    set -- "$@" --tools
    remaining=$tools
    while [ -n "$remaining" ]; do
        tool=${remaining%%,*}
        set -- "$@" "$tool"
        case "$remaining" in *,*) remaining=${remaining#*,} ;; *) remaining= ;; esac
    done
fi
[ "$dry_run" = false ] || set -- "$@" --dry-run
[ "$replace_modified" = false ] || set -- "$@" --replace-modified
printf '%s project %s with kit %s (commit %s)\n' "$mode" "$project" "$actual_version" "$commit" >&2
"$@" </dev/null
if [ "$dry_run" = false ]; then
    printf 'Ready. Restart your agent CLI in the project to load commands/skills.\n' >&2
fi

# Elm Multi-Architecture Toolchain Support

This directory provides multi-architecture support for building Elm binaries in Bazel on `linux-arm64` (aarch64-linux) host machines, in addition to standard `linux-amd64` (x86_64-linux) hosts.

## Background

The standard `@rules_elm` (v1.1.1) module includes built-in toolchains for `x86_64-linux`, `x86_64-darwin`, and `aarch64-darwin`. However, official Elm releases do not publish an `aarch64-linux` binary, so `@rules_elm` does not provide an `aarch64-linux` toolchain out-of-the-box.

To support development on `linux-arm64` hosts without modifying `@rules_elm` via patch files, a custom Bzlmod module extension is defined in [`extension.bzl`](file:///usr/local/google/home/kayce/kaycebasques.net/tools/elm/extension.bzl).

## How It Works

### 1. ARM64 Compiler Download & Extraction
The [`extension.bzl`](file:///usr/local/google/home/kayce/kaycebasques.net/tools/elm/extension.bzl) extension defines a repository rule `elm_aarch64_linux_repository` that:
- Downloads the community-maintained Elm 0.19.1 ARM64 Linux binary (`binary-for-linux-arm-64-bit-recommended.gz`).
- Decompresses the binary using `@rules_elm//tools/gzip:bin`.
- Wraps the binary in an `elm_toolchain` target (`:elm_toolchain_info`).
- Declares a Bazel `toolchain` with execution platform constraints:
  ```bzl
  exec_compatible_with = [
      "@platforms//os:linux",
      "@platforms//cpu:aarch64",
  ]
  ```

### 2. Automatic Toolchain Selection
The toolchain is registered in [`MODULE.bazel`](file:///usr/local/google/home/kayce/kaycebasques.net/MODULE.bazel):

```bzl
elm_arm64 = use_extension("//tools/elm:extension.bzl", "elm_arm64")
use_repo(elm_arm64, "elm_aarch64_linux")
register_toolchains("@elm_aarch64_linux//:toolchain")
```

Bazel resolves the appropriate toolchain automatically based on the host execution platform:

- **On `linux-amd64` (x86_64) hosts**: Bazel checks `@elm_aarch64_linux//:toolchain`. Because `cpu:aarch64` does not match the `x86_64` host execution platform, Bazel skips it and selects `@rules_elm`'s default `x86_64-linux` toolchain.
- **On `linux-arm64` (aarch64) hosts**: Bazel matches `os:linux` and `cpu:aarch64` against `@elm_aarch64_linux//:toolchain`. Since `@rules_elm` lacks a default `aarch64-linux` toolchain, Bazel selects `@elm_aarch64_linux//:toolchain` and compiles using the native ARM64 Elm binary.

def _elm_aarch64_linux_repository_impl(ctx):
    ctx.download(
        url = "https://github.com/lydell/compiler/releases/download/0.19.1/binary-for-linux-arm-64-bit-recommended.gz",
        sha256 = "978ca677abc6ae27cface7468858adb782bd302730c7c564ff1b784a4a5b9235",
        output = "compiler.gz",
    )
    ctx.file(
        "BUILD.bazel",
        content = """load("@rules_elm//elm/private:elm_toolchain.bzl", "elm_toolchain")

genrule(
    name = "extract_elm_compiler",
    srcs = [":compiler.gz"],
    outs = ["compiler"],
    tools = ["@rules_elm//tools/gzip:bin"],
    cmd = "$(execpath @rules_elm//tools/gzip:bin) $(SRCS) $@",
)

elm_toolchain(
    name = "elm_toolchain_info",
    elm = ":extract_elm_compiler",
    visibility = ["//visibility:public"],
)

toolchain(
    name = "toolchain",
    exec_compatible_with = [
        "@platforms//os:linux",
        "@platforms//cpu:aarch64",
    ],
    toolchain = ":elm_toolchain_info",
    toolchain_type = "@rules_elm//elm:toolchain",
    visibility = ["//visibility:public"],
)
""",
    )

elm_aarch64_linux_repository = repository_rule(
    implementation = _elm_aarch64_linux_repository_impl,
)

def _elm_arm64_extension_impl(ctx):
    elm_aarch64_linux_repository(name = "elm_aarch64_linux")

elm_arm64 = module_extension(
    implementation = _elm_arm64_extension_impl,
)

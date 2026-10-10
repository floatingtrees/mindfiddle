from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            "mindfiddle._core",
            sources=["optimized/core.c"],
            extra_compile_args=["-O3"],
        )
    ]
)

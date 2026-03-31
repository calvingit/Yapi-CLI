from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-yapi",
    version="0.1.0",
    description="CLI-Anything harness for YApi — query and manage YApi interfaces from the command line",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.yapi": ["skills/*.md"],
    },
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-yapi=cli_anything.yapi.yapi_cli:cli",
        ],
    },
    python_requires=">=3.10",
)

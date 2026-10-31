import os
import pathlib
from sys import version_info, exit
from setuptools import setup, find_packages
from pkg_resources import parse_requirements


def write_version_py():
    with open(os.path.join("IndicTransToolkit", "version.txt"), "r") as f:
        version = f.read().strip()

    with open(os.path.join("IndicTransToolkit", "version.py"), "w") as f:
        f.write(f'__version__ = "{version}"\n')
    return version


if version_info < (3, 8):
    exit("Sorry, Python >= 3.8 is required for IndicTransToolkit.")


with open("README.md", "r", errors="ignore", encoding="utf-8") as fh:
    long_description = fh.read().strip()

version = write_version_py()

setup(
    name="IndicTransToolkit",
    version=version,
    author="Varun Gumma",
    author_email="varun230999@gmail.com",
    description="A simple, consistent, and extendable module for IndicTrans2 tokenizer compatible with the HuggingFace models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/VarunGumma/IndicTransToolkit",
    packages=find_packages(),
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        str(requirement)
        for requirement in parse_requirements(pathlib.Path(f"requirements.txt").open())
    ],
)

import codecs

from setuptools import setup, find_packages

with codecs.open("README.md", encoding="utf-8") as f:
    readme = f.read()

# Read dependencies from requirements.txt
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="cloudimized",
    version="2.0.1",
    description='GCP & Azure configuration scanning tool',
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/egnyte/cloudimized",
    author="Egnyte and Contributors",
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
    ],
    packages=find_packages(),
    package_data={
        "": ["LICENSE", "*.md", "config-example.yml"],
        "cloudimized": ["singlerunconfigs/*.yaml"]
    },
    include_package_data=True,
    install_requires=requirements,
    extras_require={
        "test": [
            'mock',
            'time_machine',
        ],
    },
    entry_points={
        "console_scripts": [
            "cloudimized=cloudimized.core.run:run",
        ],
    },
)

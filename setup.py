import codecs

from setuptools import setup, find_packages

with codecs.open("README.md", encoding="utf-8") as f:
    readme = f.read()

setup(
    name="cloudimized",
    version="1.3.0rc1",
    description='Google Cloud Platform (GCP) configuration scanning tool',
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/egnyte/cloudimized",
    author="Egnyte and Contributors",
    classifiers=[
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
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
    install_requires=[
        'cachetools==4.2.4',
        'certifi==2021.10.8',
        'cffi==1.15.0',
        'charset-normalizer==2.0.9',
        'cryptography==36.0.1',
        'defusedxml==0.7.1',
        'flatdict==4.0.1',
        'gitdb==4.0.9',
        'GitPython==3.1.27',
        'google-api-core==2.3.2',
        'google-api-python-client==2.33.0',
        'google-auth==2.3.3',
        'google-auth-httplib2==0.1.0',
        'google-cloud-appengine-logging==1.1.0',
        'google-cloud-audit-log==0.2.0',
        'google-cloud-core==2.2.1',
        'google-cloud-logging==2.7.0',
        'googleapis-common-protos==1.54.0',
        'grpc-google-iam-v1==0.12.3',
        'grpcio==1.43.0',
        'grpcio-status==1.43.0',
        'httplib2==0.20.2',
        'idna==3.3',
        'importlib-metadata==4.11.2',
        'jeepney==0.7.1',
        'jira==3.1.1',
        'keyring==23.5.0',
        'mock==4.0.3',
        'oauthlib==3.2.0',
        'packaging==21.3',
        'proto-plus==1.19.8',
        'protobuf==3.19.1',
        'pyasn1==0.4.8',
        'pyasn1-modules==0.2.8',
        'pycparser==2.21',
        'pyparsing==3.0.6',
        'python-dateutil==2.8.2',
        'PyYAML==6.0',
        'requests==2.26.0',
        'requests-oauthlib==1.3.1',
        'requests-toolbelt==0.9.1',
        'rsa==4.8',
        'SecretStorage==3.3.1',
        'six==1.16.0',
        'slack-sdk==3.13.0',
        'smmap==5.0.0',
        'terrasnek==0.1.7',
        'time-machine==2.5.0',
        'typing-extensions==4.0.1',
        'uritemplate==4.1.1',
        'urllib3==1.26.7',
        'zipp==3.7.0',
    ],
    extras_require={
        "test": [
            'mock',
        ],
    },
    entry_points={
        "console_scripts": [
            "cloudimized=cloudimized.core.run:run",
        ],
    },
)

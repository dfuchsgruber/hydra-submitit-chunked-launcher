from setuptools import setup, find_namespace_packages

install_requires = [
    "hydra-core>=1.1.1",
    'submitit'
]

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='hydra_submitit_chunked',
    version='0.0.1',
    description='Hydra plugin using submitit that allows chunking jobs',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Dominik Fuchsgruber',
    author_email='d.fuchsgrber@tum.de',
    packages=find_namespace_packages(include=["hydra_plugins.*"]),
    classifiers=[
        "License :: OSI Approved :: MIT Apache License, Version 2.0",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    include_package_data=True,
    entry_points={
            'console_scripts': [
            ]
    },
    install_requires=install_requires,
    python_requires='>=3.7',
    zip_safe=False,
)
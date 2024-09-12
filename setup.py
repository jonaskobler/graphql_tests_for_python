from setuptools import setup, find_packages

with open("requirements.txt") as f:
    required = f.read().splitlines()

setup(
    name="testemate",
    version="0.1.0",
    description="A module with pytest fixtures",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(where='src'),
    package_dir={"": "src"},
    install_requires=required,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)

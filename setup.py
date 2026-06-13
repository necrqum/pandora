from setuptools import setup, find_packages

setup(
    name="pandora",
    version="0.2.0",
    description="A self-hosted, fully encrypted media organizer web app.",
    author="Necrqum",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi",
        "uvicorn",
        "cryptography",
        "sqlalchemy",
        "pydantic",
        "sqlcipher3-binary"
    ],
    entry_points={
        "console_scripts": [
            "pandora=pandora.backend.main:start",
        ],
    },
)

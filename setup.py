import setuptools
import pathlib

topdir = pathlib.Path(__file__).parent


def readfile(f):
    return (topdir / f).read_text("utf-8").strip()


setuptools.setup(
    name="websocket-rooms",
    version="0.1.0",
    description="Python library for simple websocket managment",
    long_description=readfile("README.md"),
    url="https://github.com/yoelbassin/Websocket-Rooms",
    author="Yoel Bassin",
    author_email="bassin.yoel@gmail.com",
    license="MIT",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
    ],
    packages=["websocket_rooms"],
    install_requires=["starlette"],
    extras_require={
        "test": [
            "fastapi",
            "pytest",
            "pytest-asyncio",
            "async-asgi-testclient",
            "flake8",
            "isort",
            "black",
        ],
        "example": ["fastapi", "uvicorn", "websockets"],
    },
)

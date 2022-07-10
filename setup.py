import setuptools
import pathlib

topdir = pathlib.Path(__file__).parent

def readfile(f):
    return (topdir / f).read_text("utf-8").strip()

setuptools.setup(
    name="websocket-rooms",
    version="0.0.1",
    description="Python library for simple websocket managment",
    # long_description=readfile("README.md"),
    url="https://github.com/yoelbassin/Websocket-Rooms",
    author="Yoel Bassin",
    author_email="bassin.yoel@gmail.com",
    license="MIT",
    classifiers=[
        "Development Status :: 1 - Planning"
        "Intended Audience :: Developers",
        "Framework :: AsyncIO, Starlette",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
    ],
    # package_data={"websocket-rooms": ["*.pyi", "py.typed"]},
    # include_package_data=True,
    packages=["websocket_rooms"],
    python_requires=">=3.5",
    install_requires=[
        "starlette"
    ],
    extras_require={"test": [
        "fastapi", "pytest", "pytest-asyncio"
    ]},
)
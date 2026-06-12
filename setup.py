from setuptools import setup, find_packages

setup(
    name="schema_router",
    license="MIT",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[],
    author="Nelson Corrocher",
    author_email="nelson.corrocher@pythonicslnet",
    description="A shortest method to get the optimal tables subset from a bigger schema.",
    url="https://github.com/nelsonwcf/schema_router",
)
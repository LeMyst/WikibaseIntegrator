from setuptools import setup

VERSION = "0.10.0.dev0"

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='wikibaseintegrator',
    version=VERSION,
    author='Myst and WikidataIntegrator authors',
    description='Python package for reading from and writing to a Wikibase instance',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='MIT',
    keywords='Wikibase',
    url='https://github.com/LeMyst/WikibaseIntegrator',
    packages=['wikibaseintegrator'],
    python_requires='>=3.7',
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Development Status :: 4 - Beta",
        "Operating System :: POSIX",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Developers",
        "Topic :: Utilities",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    install_requires=[
        'simplejson',
        'requests',
        'pandas',
        'mwoauth',
        'backoff'
    ],
    extras_require={
        'dev': [
            'pytest'
        ]
    }
)

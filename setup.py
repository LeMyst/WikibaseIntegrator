from setuptools import setup, find_packages

VERSION = "0.8.2"

setup(
    name='wikibaseintegrator',
    version=VERSION,
    author='Myst and WikidataIntegrator authors',
    description='Python package for reading and writing to/from Wikibase',
    license='MIT',
    keywords='Wikibase',
    url='https://github.com/LeMyst/WikibaseIntegrator',
    packages=find_packages(),
    include_package_data=True,
    # long_description=read('README.md'),
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Development Status :: 4 - Beta",
        "Operating System :: POSIX",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Developers",
        "Topic :: Utilities",
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

from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

import versioneer

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='shipami',

    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass().copy(),

    description='CLI tool to manage AWS AMI and Marketplace',
    long_description=long_description,

    url='http://github.com/wnkz/shipami',
    download_url='https://github.com/wnkz/shipami/archive/{}.tar.gz'.format(versioneer.get_version()),

    author='wnkz',
    author_email='wnkz@users.noreply.github.com',

    license='MIT',

    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',

        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],

    keywords='aws ec2 ami marketplace',

    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    install_requires=[
        'click',
        'botocore',
        'boto3'
    ],

    entry_points={
        'console_scripts': [
            'shipami=shipami.cli:cli',
        ],
    },

    zip_safe=False
)

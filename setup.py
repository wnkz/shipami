from setuptools import setup, find_packages

import versioneer

setup(
    name='shipami',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass().copy(),
    description='CLI tool to manage AWS AMI and Marketplace',
    url='http://github.com/wnkz/shipami',
    author='wnkz',
    author_email='wnkz@users.noreply.github.com',
    license='MIT',
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    zip_safe=False,
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
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
    ]
)

import setuptools
import os

from lslopt.cli import VERSION


mydir = os.path.dirname(__file__)
with open(os.path.join(mydir, 'README.md'), 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='lsl-optimizer',
    version=VERSION,
    description='Optimize LSL2 scripts',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Sei-Lisa/LSL-PyOptimizer',
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    install_requires=[
        'pcpp>=1.3,<2',
    ],
    entry_points={
        'console_scripts': ['lslopt = lslopt.cli:main'],
    },
)

import setuptools
import os

from lslopt.cmd import VERSION


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
    packages=['lslopt', 'strutil'],
    package_data={
        'lslopt': ['data/*.txt'],
    },
    include_package_data=True,
    install_requires=[],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    entry_points={
        'console_scripts': ['lslopt = lslopt.cmd:main'],
    },
)

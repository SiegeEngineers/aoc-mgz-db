"""MGZ DB setup."""
from setuptools import setup, find_packages

setup(
    name='mgzdb',
    version='0.0.1',
    description='Age of Empires II recorded game database.',
    url='https://github.com/siegeengineers/aoc-mgz-db/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=find_packages(),
    install_requires=[
        'coloredlogs>=10.0',
        'iso8601>=0.1.12',
        'mgz>=1.1.5',
        'requests>=2.20.1',
        'scp>=0.13.0',
        'SQLAlchemy>=1.2.14',
        'voobly>=1.2.3'
    ],
    entry_points = {
        'console_scripts': ['mgzdb=mgzdb.__main__:setup'],
    },
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ]
)

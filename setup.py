"""MGZ DB setup."""
from setuptools import setup, find_packages

setup(
    name='mgzdb',
    version='1.2.5',
    description='Age of Empires II recorded game database.',
    url='https://github.com/siegeengineers/aoc-mgz-db/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=find_packages(),
    package_data={'mgzdb': [
        'metadata/*.json',
    ]},
    install_requires=[
        'alembic>=1.0.8',
        'aocref>=0.0.3',
        'python-aoc-qq>=1.0.1',
        'coloredlogs>=10.0',
        'iso8601>=0.1.12',
        'mgz>=1.2.5',
        'requests>=2.20.1',
        'requests-cache>=0.4.13',
        'SQLAlchemy>=1.2.14',
        'tqdm>=4.28.1',
        'voobly>=1.2.9'
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

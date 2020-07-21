"""MGZ DB setup."""
from setuptools import setup, find_packages

setup(
    name='mgzdb',
    version='1.3.12',
    description='Age of Empires II recorded game database.',
    url='https://github.com/siegeengineers/aoc-mgz-db/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=find_packages(),
    install_requires=[
        'coloredlogs==10.0',
        'mgz>=1.4.7',
        'psycopg2-binary==2.8.4',
        'python-aoc-qq>=1.0.4',
        'rarfile==3.1',
        'SQLAlchemy==1.3.12',
        'voobly>=1.3.1'
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

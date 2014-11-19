#!/usr/bin/env python
from setuptools import setup, find_packages
import os


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='django-xss-detection',
    author='David Black',
    author_email='dblack@atlassian.com',
    url='https://bitbucket.org/atlassian/django_xss_detection',
    packages=find_packages(),
    description=read('README.md'),
    long_description=read('README.md'),
    version=__import__('django_xss_detection').__version__,
    test_suite='django_xss_detection.test',
    install_requires=[
        'Django>=1.5',
        'lxml',
    ],
    platforms=['any'],
    license='BSD',
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'License :: OSI Approved :: BSD License',
        'Framework :: Django',
    ],
)

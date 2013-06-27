#!/usr/bin/env python
from setuptools import setup, find_packages
import os

def read(fname):
	return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(name='django_xss_detection',
	author='david black',
	author_email='dblack@atlassian.com',
	url='https://bitbucket.org/atlassian/django_xss_detection',
	packages=find_packages(),
	description=read('README.md'),
	long_description=read('README.md'),
	version = __import__('django_xss_detection').__version__
)


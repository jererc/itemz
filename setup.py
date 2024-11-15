from setuptools import setup, find_packages

setup(
    name='itemz',
    version='0.1.0',
    author='jererc',
    author_email='jererc@gmail.com',
    url='https://github.com/jererc/itemz',
    packages=find_packages(exclude=['tests']),
    python_requires='>=3.10',
    install_requires=[
        'svcutils @ git+https://github.com/jererc/svcutils.git@main#egg=svcutils',
        'webutils @ git+https://github.com/jererc/webutils.git@main#egg=webutils',
    ],
    extras_require={
        'dev': ['flake8', 'pytest'],
    },
    include_package_data=True,
)

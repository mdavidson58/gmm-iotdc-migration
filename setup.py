from setuptools import setup, find_packages

setup(
    name="gmm-app-migration",
    version="1.0.0",
    author="Cisco",
    author_email="admin@cisco.com",
    description="Migrating an application from GMM to IOT-OD",
    url="https://cto-github.cisco.com/IOTNM/gmm-iotoc-migration",
    project_urls={
        "Bug Tracker": "https://cto-github.cisco.com/IOTNM/gmm-iotoc-migration",
    },
    packages=find_packages(),
    py_modules=['migrate', 'app_migration'],
    include_package_data=True,
    install_requires=[
        'Click',
        'requests',
        'PyYAML',
        'tabulate',
        'paramiko==2.7.2',
        'scp==0.13.3',
        'urllib3==1.26.4'
    ],
    entry_points={
        'console_scripts': [
            'migrate=migrate:migrate',
        ],
    },
    python_requires=">=3.6",
)

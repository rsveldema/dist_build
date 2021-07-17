import setuptools

""""
setuptools.setup(
    name='dist_build',
    version='0.0.1',
    packages=['dist_build'],
    install_requires=[
        'requests',
        'importlib; python_version == "3.8"',
    ],
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        "": ["*.json", "*.rst"]
    }
)
"""

setuptools.setup(
    name='dist_build',
    version='0.0.1',
    packages=['dist_build']
    )
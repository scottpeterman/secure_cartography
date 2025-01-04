from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_path = Path("README.md")
long_description = readme_path.read_text(encoding="utf-8")

# Read requirements file
requirements_path = Path("requirements.txt")
requirements = [
    line.strip()
    for line in requirements_path.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]

setup(
    name="secure-cartography",
    version="0.8.2",
    author="Scott Peterman",
    author_email="scottpeterman@gmail.com",
    description="A secure, Python-based network discovery and mapping tool using SSH-based device interrogation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/scottpeterman/secure_cartography",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Environment :: X11 Applications",
        "Topic :: System :: Networking",
        "Topic :: System :: Monitoring",
        "Topic :: Security",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    package_data={
        "secure_cartography": [
            "tfsm_templates.db",
            "resources/index.html",
            "resources/splash.jpeg"
        ],
    },
    include_package_data=True,
    entry_points={
        'gui_scripts': [
            'scart=secure_cartography.scart:main',
            'merge-dialog=secure_cartography.merge_dialog:main',
            'mviewer=secure_cartography.mviewer:main',

        ],
        'console_scripts': ['sc=secure_cartography.sc:main']
    },
)
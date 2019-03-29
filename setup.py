from setuptools import setup, find_packages
from codecs import open
from os import path


here = path.abspath(path.dirname(__file__))

about = {}
with open(path.join(here, 'openSeSSHIAMe', '__about__.py')) as fp:
    exec(fp.read(), about)

__version__ = about['__version__']
PROJECT_URL = 'https://gitlab.com/vedvyas/openSeSSHIAMe'

setup(
    # TODO: move all of this metadata to __about__.py?
    name='openSeSSHIAMe',
    version=__version__,

    description='''openSeSSHIAMe allows SSH access to an instance behind the
    great AWS firewall (security group for the instance) for authorized IAM
    users from their current location.''',
    long_description=open(path.join(here, 'README.md'),
                          encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    keywords='AWS IAM SSH security-group boto3',

    license='MIT',

    author='Ved Vyas',
    author_email='ved@vyas.io',

    url=PROJECT_URL,
    download_url='%s/repository/archive.tar.bz2?ref=v%s' % (PROJECT_URL,
                                                            __version__),

    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: System :: Networking',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3'
    ],

    install_requires=[
        'boto3 >= 1.9.121',
        'docopt >= 0.6.2',
        'requests >= 2.21.0'
    ],

    packages=find_packages(),
    package_data={
        'openSeSSHIAMe': ['README.md', 'COPYING',
                          'etc/openSeSSHIAMe-config.json',
                          'etc/openSeSSHIAMe-oneshot.service',
                          'etc/openSeSSHIAMe-oneshot.timer']
    },

    entry_points={
        'console_scripts': [
            'openSeSSHIAMe = openSeSSHIAMe.openSeSSHIAMe:main'
        ]
    }
)

openSeSSHIAMe
=============

Intro
-----

openSeSSHIAMe (picture Adam Sandler singing "open sesame") allows SSH access to
an instance behind the great AWS firewall (security group for the instance) for
authorized users from their current location.

Given the credentials for an AWS IAM (Identity and Access Management) user, it:

  * Obtains the current machine's public IP address
  * Uses the AWS Python SDK (boto3) to allow incoming traffic to the instance
    on port 22 from the public IP address
  * Revokes previous ingress rules for this IAM user

Disclaimer
----------

Use at your own risk, and only with trusted users. Follow best practices to
secure your EC2 instance and AWS account. Feedback, suggested improvements, and
contributions will be most appreciated. See [Notes](#notes) for known issues
with the current implementation.

AWS Prerequisites
-----------------

  * An EC2 instance with at least one associated security group that
    openSeSSHIAMe can operate on. It's probably a good idea to keep a dedicated
    security group for use with this tool.
  * For each openSeSSHIAMe user, an IAM user that:
    * Has an attached tag with `Key=openSeSSHIAMe-ID` and a unique `Value`
      among all openSeSSHIAMe users
    * Allows the following EC2 actions only on that particular security group:
        * `DescribeSecurityGroups` (List)
        * `AuthorizeSecurityGroupIngress` (Write)
        * `RevokeSecurityGroupIngress` (Write)
    * Allows the following IAM actions only on that particular IAM user (this
      can be achieved by using `${aws:username}` in the ARN when specifying
      resources):
        * `ListUserTags` (List)

Notes
-----

  * The IAM user will be able to describe security groups other than the one
    used by openSeSSHIAMe! This is because `DescribeSecurityGroups` cannot be
    restricted to a particular resource (the security group used by
    openSeSSHIAMe).
  * The service used to determine the current public IPv4 address could return
    an incorrect address, thus giving someone else access!

Requirements
------------

  * Python 3+
  * boto3 (>= 1.9.121)
  * docopt (>= 0.6.2)
  * requests (>= 2.21.0)

Installation
------------

To install from source, execute the following in the directory containing
`setup.py`:

    pip install [--user] [--upgrade] .

To install from `PyPI`:

    pip install [--user] [--upgrade] openSeSSHIAMe

Usage
-----

The openSeSSHIAMe CLI can be executed for oneshot authorization of the user's
current public IPv4 address:

    openSeSSHIAMe --verbose --config /path/to/config.json

Here, `config.json` should look like `etc/openSeSSHIAMe-config.json`, found in
this repo and the installed package. It consists of the IAM credentials and
username for the current openSeSSHIAMe user, the ID of the security group to
use, and the region the EC2 instance is running in.

openSeSSHIAMe can be run at the time of starting an SSH session, just like
[port-knockers][1]. One way is using `ProxyCommand` in your SSH client
config:

    Host foo
    HostName ...
    ...
    ProxyCommand bash -c 'openSeSSHIAMe --verbose --config ...; sleep 1;
                          exec nc %h %p'

This technique should also work with autossh.

Alternatively (or additionally), a sample systemd service and timer for
periodic execution are included in `etc/`.

Finally, feel free to import and use the `openSeSSHIAMe` class after installing
this package:

    from openSeSSHIAMe import openSeSSHIAMe
    sesame = openSeSSHIAMe(config_filename='...', verbose=True)
    # See main() in openSeSSHIAMe.py for further usage

TODO
----

  * If an existing rule for the current public IP address exists, don't revoke
    and re-authorize it -- just to reduce entries in CloudTrail. However, calls
    to `DescribeSecurityGroups` and `ListUserTags` are unavoidable.
  * Allow ports other than 22 and multiple ports. Might do this if and when the
    need arises.
  * Allow for multiple address per IAM user. Ditto.
  * Use PID file to handle concurrent runs for same IAM user.
  * Add option to use IPv6 addresses.

License
-------

openSeSSHIAMe is distributed under the terms of the MIT license. Please see
COPYING.

[1]: https://lzone.de/blog/Port%20Knocking%20And%20SSH%20ProxyCommand

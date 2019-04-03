#!/usr/bin/env python3
'''
openSeSSHIAMe: allow SSH access to an instance behind the great AWS firewall
(security group for the instance) for authorized IAM users from their current
location

Copyright (c) 2019 Ved Vyas

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Usage:
  openSeSSHIAMe [-v] --config FILENAME
  openSeSSHIAMe (-h | --help | --version)

Options:
  --config FILENAME              JSON configuration file to use
  -v --verbose                   Print additional information
  -h --help                      Show this screen
  --version                      Show version

See the README for information on the configuration files and usage.
'''


import copy
import json

from docopt import docopt
import boto3
import requests

from .__about__ import __version__


class openSeSSHIAMe:
    '''
    An `openSeSSHIAMe` instance can manage ingress rules in an AWS security
    group for a particular IAM user. `openSeSSHIAMe` tracks users through tags
    on each IAM user (with a `Key` of `openSeSSHIAMe-ID`).

    Using the public methods, one can list and revoke existing rules for an
    `openSeSSHIAMe` user (e.g., ingress that was previously authorized from a
    different location). Then one can authorize ingress from the current public
    IPv4 address.

    For typical usage, see `main`.
    '''
    def __init__(self, config_filename, **kwargs):
        '''Initialize a ready-to-use openSeSSHIAMe instance.

        Args:
            config_filename (str): Path to the JSON configuration file. See
                etc/openSeSSHIAMe-config.json in this package for its expected
                format.
            **kwargs:
                verbose (bool, optional): Additional info printed to stdout if
                    True
        '''
        self.verbose = kwargs.get('verbose', False)

        with open(config_filename, 'r') as config_file:
            self.config = config = json.loads(config_file.read())

        # TODO: check that config contains the necessary entries

        self.session = boto3.Session(
            aws_access_key_id=config['aws_access_key_id'],
            aws_secret_access_key=config['aws_secret_access_key'])

        self.IAM = self.session.client('iam')
        self.EC2 = self.session.client('ec2',
                                       region_name=self.config['aws_region'])

    def list_existing_ingress_rules(self):
        '''List existing ingress rules for the current openSeSSHIAMe user.

        This uses openSeSSHIAMe's bookeeping method to only return rules
        generated by openSeSSHIAMe. This method can handle existing rules that
        are present as multiple `IpRanges` elements within one `IpPermissions`
        element in the configured security group.

        Returns:
            list: List of rules. Each element of rules -- a rule -- should be
                structured like an element of `IpPermissions` in the boto3
                API. As an example:

                {
                  "FromPort": 22,
                  "IpProtocol": "tcp",
                  "IpRanges": [
                    {
                      "CidrIp": "10.0.0.1/32",
                      "Description": "A description. Take a look at
                                     `_generate_ingress_rule_description()` to
                                     see how this is used by openSeSSHIAMe."
                    }
                  ],
                  "Ipv6Ranges": [],
                  "PrefixListIds": [],
                  "ToPort": 22,
                  "UserIdGroupPairs": []
                }

                For more information on the structure of `IpPermissions`, see:
                https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.authorize_security_group_ingress
        '''
        sec_groups = self.EC2.describe_security_groups(
            GroupIds=[self.config['security_group_ID']])
        assert len(sec_groups['SecurityGroups']) == 1
        sec_group = sec_groups['SecurityGroups'][0]

        ingress_rule_description = self._generate_ingress_rule_description()

        if self.verbose:
            print('Finding existing ingress rules for %s...' %
                  ingress_rule_description)

        # Build list of existing ingress rules for current openSeSSHIAMe user
        existing_rules = []
        for rule in sec_group['IpPermissions']:
            # Sometimes multiple rules (as seen from the AWS console) are
            # present as multiple IpRanges elements within one IpPermissions
            # element, so we'll make a template rule to populate with only the
            # IpRange of interest. This should help avoid revoking rules that
            # are not managed by openSeSSHIAMe, for instance.
            rule_template = copy.deepcopy(rule)
            rule_template['IpRanges'] = None

            for IP_range in rule['IpRanges']:
                # This is how openSeSSHIAMe-managed rules for the current IAM
                # user are tracked
                if IP_range['Description'] == ingress_rule_description:
                    existing_rule = copy.deepcopy(rule_template)
                    existing_rule['IpRanges'] = [IP_range]
                    existing_rules.append(existing_rule)

                    if self.verbose:
                        print('Existing rule: access to ports %d--%d from %s' %
                              (rule['FromPort'], rule['ToPort'],
                               IP_range['CidrIp']))

                    # TODO: might want to drop this break
                    break

        return existing_rules

    def revoke_ingress_rules(self, rules):
        '''Revoke ingress rules from the security group in the config.

        This method can revoke *any* rules in the security group configured by
        the current IAM user.

        See the boto3 docs for more details about how rules are matched and
        revoked:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.revoke_security_group_ingress

        Args:
            rules (list): A list of ingress rules to revoke.
        '''
        if not rules:
            return

        # TODO: check response
        self.EC2.revoke_security_group_ingress(
            GroupId=self.config['security_group_ID'],
            IpPermissions=rules)

    def authorize_ingress_rules(self, rules):
        '''Authorize ingress rules for security group in configuration.

        This does not use openSeSSHIAMe's bookeeping method to facilitate
        subsequent tracking of these rules -- that's up to the caller of this
        method.
        '''
        # TODO: check response
        self.EC2.authorize_security_group_ingress(
            GroupId=self.config['security_group_ID'],
            IpPermissions=rules)

    # TODO: accept protocol, port range, IPv6, etc.
    def generate_ingress_rule(self, port, IPv4_CIDR=None):
        '''Generate ingress rule, from current public IP address to the
        specified port, for use with `authorize_ingress_rules`

        This grabs the current public IPv4 address and uses openSeSSHIAMe's
        bookeeping method to facilitate subsequent tracking of this rule.

        Args:
            port (int): The port to allow incoming traffic to.
            IPv4_CIDR (str, optional): If provided, a source IPv4 CIDR range to
                allow incoming traffic from. Otherwise, the current public IPv4
                address is used.

        Returns:
            dict: A rule to pass to `authorize_ingress_rules`. See
            `revoke_ingress_rules` for its format.

        Raises:
            Some exceptions: If the public IP address cannot be determined, or
                if there is a problem obtaining the openSeSSHIAMe ID.
        '''
        if not IPv4_CIDR:
            IPv4_CIDR = self._get_public_IPv4_address() + '/32'
        # TODO: check that IPv4_CIDR is valid
        ingress_rule_description = self._generate_ingress_rule_description()

        if self.verbose:
            print('Generating ingress rule for port %d from %s for %s' % (
                port, IPv4_CIDR, ingress_rule_description))

        # Attempt to authorize ingress on port 22 from current address
        return {
            'IpProtocol': 'tcp',
            'FromPort': port,
            'ToPort': port,
            'IpRanges': [{
                'CidrIp': IPv4_CIDR,
                'Description': ingress_rule_description
            }]
        }

    def _generate_ingress_rule_description(self):
        'Generate ingress rule description for openSeSSHIAMe bookeeping.'
        return 'openSeSSHIAMe-' + self._get_openSeSSHIAMe_ID()

    def _get_public_IPv4_address(self):
        'Get public IPv4 address.'
        try:
            res = requests.get('https://api.ipify.org')
            if res.status_code == 200:
                return res.text

        except Exception as e:
            print('Can not determine public IP address')
            raise e

        raise RuntimeError(
            'Can not determine public IP address, status code: '
            + str(res.status_code))

    def _get_openSeSSHIAMe_ID(self):
        '''Get value of IAM tag that describes the current IAM user's
        openSeSSHIAMe ID.'''
        IAM_user_tags = self.IAM.list_user_tags(
            UserName=self.config['aws_iam_username'])

        for tag in IAM_user_tags['Tags']:
            if tag['Key'] == 'openSeSSHIAMe-ID':
                return tag['Value']

        raise RuntimeError(
            '''Could not get a unique ID for openSeSSHIAMe to use, check that
            your IAM user has an attached tag with "Key"="openSeSSHIAMe-ID" and
            a unique "Value" among all openSeSSHIAMe users''')


def main():
    args = docopt(__doc__, version='openSeSSHIAMe v' + __version__)

    verbose = args.get('--verbose', False)
    config_filename = args['--config']

    sesame = openSeSSHIAMe(config_filename=config_filename, verbose=verbose)

    # TODO: if the current public IP address is already authorized, filter it
    # out before revoking and then there's no need to re-authorize it.
    existing_rules = sesame.list_existing_ingress_rules()
    sesame.revoke_ingress_rules(existing_rules)

    new_SSH_rule = sesame.generate_ingress_rule(22)
    sesame.authorize_ingress_rules([new_SSH_rule])


if __name__ == '__main__':
    main()

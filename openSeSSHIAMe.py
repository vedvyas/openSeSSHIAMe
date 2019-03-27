#!/usr/bin/env python3

import boto3
import requests

import copy
import json


class openSeSSHIAMe:
    def __init__(self, config_filename, **kwargs):
        self.verbose = kwargs.get('verbose', False)

        with open(config_filename, 'r') as config_file:
            self.config = config = json.loads(config_file.read())

        # Check that config contains the necessary entries

        self.session = boto3.Session(
            aws_access_key_id=config['aws_access_key_id'],
            aws_secret_access_key=config['aws_secret_access_key'])

    def revoke_existing_ingress_rules(self):
        EC2 = self.session.client('ec2', region_name=self.config['aws_region'])

        sec_groups = EC2.describe_security_groups(
            GroupIds=[self.config['security_group_ID']])
        assert len(sec_groups['SecurityGroups']) == 1
        sec_group = sec_groups['SecurityGroups'][0]

        ingress_rule_description = self._generate_ingress_rule_description()

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

                    break

        # Attempt to remove existing ingress rules for current openSeSSHIAMe
        # user
        if len(existing_rules):
            EC2.revoke_security_group_ingress(
                GroupId=self.config['security_group_ID'],
                IpPermissions=existing_rules)

    def authorize_ingress_from_current_location(self):
        EC2 = self.session.client('ec2', region_name=self.config['aws_region'])

        # Attempt to authorize ingress on port 22 from current address
        EC2.authorize_security_group_ingress(
            GroupId=self.config['security_group_ID'],
            IpPermissions=[{
                'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{
                    'CidrIp': self._get_public_IPv4_address() + '/32',
                    'Description': self._generate_ingress_rule_description()
                }]
            }])

    def _generate_ingress_rule_description(self):
        return 'openSeSSHIAMe-' + self._get_openSeSSHIAMe_ID()

    def _get_public_IPv4_address(self):
        try:
            res = requests.get('https://api.ipify.org')
            if res.status_code == 200:
                return res.text

        except Exception as e:
            print('Can not determine public IP address')
            raise e

        raise RuntimeError(
            'Can not determine public IP address: ' + str(res.status_code))

    def _get_openSeSSHIAMe_ID(self):
        IAM = self.session.client('iam')
        IAM_user_tags = IAM.list_user_tags(
            UserName=self.config['aws_iam_username'])

        for tag in IAM_user_tags['Tags']:
            if tag['Key'] == 'openSeSSHIAMe-ID':
                return tag['Value']

        raise RuntimeError(
            '''Could not get a unique ID for openSeSSHIAMe to use, check that
            your IAM user has an attached tag with "Key"="openSeSSHIAMe-ID" and
            a unique "Value" among all openSeSSHIAMe users''')

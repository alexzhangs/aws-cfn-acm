#!/usr/bin/env python

'''
Validate the ACM certificate domain by maintaining DNS records.

Environment Variables:
  DOMAIN:                       Domain name for the SSL certificate.
  DOMAIN_NAMESERVER:            Domain Nameserver for Domain. Supported Nameserver: 'name.com'.
  DOMAIN_NAMESERVER_USERNAME:   User identity for the Domain Nameserver API service.
  DOMAIN_NAMESERVER_CREDENTIAL: User credential/token for the Domain Nameserver API service.
'''

import time, os, json
import boto3, botocore.vendored.requests as requests
import cfnresponse

print('Loading function')

def lambda_handler(event, context):
    try:
        domain = os.getenv('DOMAIN')
        ns = os.getenv('DOMAIN_NAMESERVER')
        ns_username = os.getenv('DOMAIN_NAMESERVER_USERNAME')
        ns_credential = os.getenv('DOMAIN_NAMESERVER_CREDENTIAL')
        requesttype = event['RequestType']

        print('request type: {}, domain: {}, nameserver: {}'.format(requesttype, domain, ns))
        api_cls_name = API_CLS_NAME.get(ns)
        api_cls = globals().get(api_cls_name)
        api = api_cls(ns_username, ns_credential)
        cert_arn = wait_call(120, 3, get_acm_cert_arn_by_domain, domain)
        acm = boto3.client('acm')
        cert = acm.describe_certificate(CertificateArn=cert_arn)['Certificate']
        for item in cert['DomainValidationOptions']:
            status = item['ValidationStatus']
            record = item['ResourceRecord']
            type = record['Type']
            name = record['Name'].rstrip('.')
            value = record['Value'].rstrip('.')
            host = get_host_from_domain(name)
            root = get_root_from_domain(name)

            if requesttype in ['Create', 'Update'] and status == 'PENDING_VALIDATION':
                api.create_record(domain=root, type=type, host=host, answer=value)
            elif requesttype == 'Delete':
                api.delete_record(domain=root, type=type, host=host)

        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
    except Exception as e:
        print(e)
        cfnresponse.send(event, context, cfnresponse.FAILED, {'error': str(e)})

def wait_call(timeout, delay, func, *args, **kwargs):
    starter = time.time()
    while (time.time() - starter) < timeout:
        ret = func(*args, **kwargs)
        if ret is not None:
            return ret
        else:
            time.sleep(delay)

def get_acm_cert_arn_by_domain(domain):
    acm = boto3.client('acm')
    for cert in acm.list_certificates()['CertificateSummaryList']:
        if cert['DomainName'] == domain:
            return cert['CertificateArn']

def get_host_from_domain(domain):
    items = domain.split('.')
    bound = len(items) - 2
    return '.'.join(items[:bound])

def get_root_from_domain(domain):
    items = domain.split('.')
    bound = len(items) - 2
    return '.'.join(items[bound:])

API_CLS_NAME = {
    'name.com': 'NameNsApi'
}

class BaseNsApi(object):
    def __init__(self, user, credential, *args, **kwargs):
        super(BaseNsApi, self).__init__(*args, **kwargs)
        self.user = user
        self.credential = credential

    def call_api(self, url, method='get', data=None):
        response = getattr(requests, method)(
            url,
            auth=(self.user, self.credential),
            json=data
        )
        return json.loads(response.text) or response

    def list_records(self, *args, **kwargs): pass
    def create_record(self, *args, **kwargs): pass
    def delete_records(self, *args, **kwargs): pass


class NameNsApi(BaseNsApi):
    api_base_url = 'https://api.name.com/v4'

    def list_records(self, domain, type, host):
        url = '/'.join([self.api_base_url, 'domains', domain, 'records'])
        records = self.call_api(url, method='get') or {}
        return [item for item in records.get('records', [])
                if item.get('type') == type and item.get('host') == host]

    def create_record(self, domain, type, host, answer, ttl=300):
        url = '/'.join([self.api_base_url, 'domains', domain, 'records'])
        data = {'host': host, 'type': type, 'answer': answer, 'ttl': ttl}
        return self.call_api(url, method='post', data=data)

    def delete_records(self, domain, type, host):
        records = self.list_records(domain, type, host)
        for item in records:
            url = '/'.join([self.api_base_url, 'domains', domain, 'records', str(item.get('id'))])
            self.call_api(url, method='delete')
        return records

    @property
    def is_accessible(self):
        try:
            url = '/'.join([self.api_base_url, 'hello'])
            return self.call_api(url, method='get').get('username') == self.user
        except:
            return False

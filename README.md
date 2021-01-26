# aws-cfn-acm

AWS CloudFormation Stack to setup AWS Certificate Manager services and
automate certificates provision.

This solution is for people who want to automate the domain validation
by DNS method without using AWS Route53 services.

This solution uses Lambda functions to leverage the DNS service
provider's API service, to automatically create DNS records to
validate the certificate domain. So far only `name.com` is supported.

NOTE:

* If you are using Route53, you don't need this.
* If you are not using `name.com` as the DNS service provider, you don't need this.

## Usage

### stack.json

This repo contains a standard AWS CloudFormation template `stack.json`
which can be deployed with AWS web console, AWS CLI or any other AWS
CloudFormation compatible tool.

Command line sample with `xsh aws/cfn/deploy`:
```sh
$ git clone https://github.com/alexzhangs/aws-cfn-acm
$ xsh aws/cfn/deploy -t aws-cfn-acm/stack.json -s AcmTest \
-o OPTIONS=Domain=www.example.com \
-o OPTIONS=DomainNameServer=name.com \
-o OPTIONS=DomainNameServerUsername=<your_username> \
-o OPTIONS=DomainNameServerCredential=<your_api_token>
```

 You may also refer to a real-world example
[aws-cfn-vpn](https://github.com/alexzhangs/aws-cfn-vpn).

For the input parameters and the detail of the template, please check the template
file.

## For Developers

1. The Lambda functions used by this template have to be inline
   Lambda functions to avoid the dependency of `xsh aws/cfn/deploy
   config`, because this template is going to be used as a nested
   template of
   [aws-cfn-vpn](https://github.com/alexzhangs/aws-cfn-vpn). 
   `aws-cfn-vpn` is able to be deployed with `xsh aws/cfn/deploy`
   which doesn't support to read `config` for the nested templates.

    Something you should know with the inline Lambda functions:

    1. Use the `pyminifier` to minimize the size of the Lambda code if
    the code size is greater than 4KB.

    ```
    pip install pyminifier
    pyminify LambdaValidateAcmDomain.py > LambdaValidateAcmDomain-pyminify.py
    ```

    1. Use `import cfnresponse` as the exact style, to let
    CloudFormation injects `cfnresponse` package for you.

1. Don't specify `HostedZoneId` in `DomainValidationOptions` if don't
need it, you only need it with AWS Route53 service involved.

```json
        "DomainValidationOptions": [{
          ...
          "HostedZoneId": ""
        }],
```

An empty option `HostedZoneId` would cause the certificate
stuck at `CREATE_IN_PROGRESS` status even the domain has been
successfully validated. 

1. The custom resource `ValidateAcmDomain` must not depend on resource
`Acm`.

The dependency will let the Lambda function code much easier to get
the `Acm` resource, but it will cause a dependency deadlock.

The dependency will cause the custom resource `ValidateAcmDomain`
never be created. it will wait forever for the `Acm` to be complete, and
which will remain in `CREATE_IN_PROGRESS` since it needs the custom
resource to validate it.

## Troubleshooting

1. The DNS records for the validation were not removed after the custom
resource is deleted.

The is because the resource `Acm` is already deleted when the custom
resource `ValidateAcmDomain` is triggering the Lambda function to
retrieve DNS records from `Acm` and delete them in the DNS service.

I don't see an elegant solution for this problem for now, tell me please if
you do.

from click.testing import CliRunner
import pytest
import os
import json

from shipami import __version__ as VERSION
from shipami.cli import cli as shipami

runner = CliRunner()

@pytest.fixture(scope='session')
def ec2():
    import boto3
    import moto

    moto.mock_ec2().start()
    return boto3.resource('ec2', region_name='eu-west-1')

@pytest.fixture(scope='class')
def base_image(ec2):
    instance = ec2.create_instances(
        ImageId='ami-42424242',
        MinCount=1,
        MaxCount=1,
        InstanceType='m4.xlarge',
        EbsOptimized=True
    )[0]

    image = instance.create_image(
        Name='foo',
        Description='Foo'
    )
    return image

class TestCli:

    def test_version(self):
        r = runner.invoke(shipami, ['--version'])

        assert r.exit_code == 0
        assert VERSION in r.output

    def test_list(self, base_image):
        r = runner.invoke(shipami, ['list'])

        assert r.exit_code == 0
        assert '{}:\t{}'.format(base_image.id, base_image.name) in r.output

    def test_release(self, ec2, base_image):
        RELEASE = '1.0.0'
        NAME = 'foo'
        image_number = len(ec2.meta.client.describe_images()['Images'])

        expected_tags = [
            {
                'Key': 'shipami:managed',
                'Value': 'True'
            },
            {
                'Key': 'shipami:release',
                'Value': '1.0.0'
            },
            {
                'Key': 'shipami:copied_from',
                'Value': 'eu-west-1:{}'.format(base_image.id)
            }
        ]

        r = runner.invoke(shipami, ['release', base_image.id, RELEASE, '--name', NAME])

        returned_image_id = r.output.strip()
        image = ec2.Image(returned_image_id)

        assert r.exit_code == 0
        assert len(ec2.meta.client.describe_images()['Images']) == image_number + 1
        assert image.name == '{}-{}'.format(NAME, RELEASE)

        assert sorted(image.tags, key=lambda _: _['Key']) == sorted(expected_tags, key=lambda _: _['Key'])

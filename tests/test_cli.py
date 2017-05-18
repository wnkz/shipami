from click.testing import CliRunner
import pytest
import os
import json
import time

from shipami import __version__ as VERSION
from shipami.cli import cli as shipami

runner = CliRunner()

@pytest.fixture()
def ec2():
    import boto3
    import moto

    moto.mock_ec2().start()
    return boto3.resource('ec2', region_name='eu-west-1')

@pytest.fixture()
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

@pytest.fixture()
def copied_image(ec2, base_image):
    time.sleep(1) # Ensure there is a CreationDate difference
    r = runner.invoke(shipami, ['copy', base_image.id])

    image_id = r.output.strip()
    image = ec2.Image(image_id)
    return image

@pytest.fixture()
def deleted_copied_image(ec2, base_image, copied_image):
    r = runner.invoke(shipami, ['delete', '-f', base_image.id])

    return copied_image

@pytest.fixture()
def released_image(ec2, base_image):
    RELEASE = '1.0.0'
    NAME = 'foo'

    time.sleep(1) # Ensure there is a CreationDate difference
    r = runner.invoke(shipami, ['release', base_image.id, RELEASE, '--name', NAME])

    image_id = r.output.strip()
    image = ec2.Image(image_id)
    return image

class TestCli:

    def test_version(self):
        r = runner.invoke(shipami, ['--version'])

        assert r.exit_code == 0
        assert VERSION in r.output

    def test_list_unmanaged(self, base_image):
        r = runner.invoke(shipami, ['list'])

        assert r.exit_code == 0
        assert base_image.id in r.output
        assert base_image.name in r.output

    def test_list(self, base_image, released_image):
        r = runner.invoke(shipami, ['list'])

        lines = r.output.splitlines()

        assert r.exit_code == 0
        assert base_image.id in lines[2]
        assert 'origin' in lines[2]
        assert 'eu-west-1:{}'.format(released_image.id) in lines[2]

        assert released_image.id in lines[1]
        assert 'origin' not in lines[1]
        assert 'eu-west-1:{}'.format(base_image.id) in lines[1]

    def test_list_aliased(self, base_image, released_image):
        r = runner.invoke(shipami, ['ls'])

        lines = r.output.splitlines()

        assert r.exit_code == 0
        assert base_image.id in lines[2]
        assert 'origin' in lines[2]
        assert 'eu-west-1:{}'.format(released_image.id) in lines[2]

        assert released_image.id in lines[1]
        assert 'origin' not in lines[1]
        assert 'eu-west-1:{}'.format(base_image.id) in lines[1]

    def test_list_quiet(self, base_image, released_image):
        r = runner.invoke(shipami, ['list', '-q'])

        lines = r.output.splitlines()

        assert r.exit_code == 0
        assert len(lines) == 2
        assert base_image.id in lines[1]
        assert released_image.id in lines[0]

    def test_list_filter_simple(self, base_image, released_image):
        r = runner.invoke(shipami, ['list', '-f', 'release=1.0.0'])

        lines = r.output.splitlines()

        assert r.exit_code == 0
        assert len(lines) == 2
        assert ' {} '.format(released_image.id) in lines[1]

    def test_list_filter_managed(self, base_image, released_image):
        r = runner.invoke(shipami, ['list', '-f', 'managed=yes'])

        lines = r.output.splitlines()

        assert r.exit_code == 0
        assert len(lines) == 2
        assert ' {} '.format(released_image.id) in lines[1]

    def test_list_filter_not_managed(self, base_image, released_image):
        r = runner.invoke(shipami, ['list', '-f', 'managed=no'])

        lines = r.output.splitlines()

        assert r.exit_code == 0
        assert len(lines) == 2
        assert ' {} '.format(base_image.id) in lines[1]

    def test_list_filter_bad(self, base_image, released_image):
        r = runner.invoke(shipami, ['list', '-f', 'invalid'])

        assert r.exit_code == 2
        assert 'Invalid value' in r.output

    def test_list_filter_unknown(self, base_image, released_image):
        r = runner.invoke(shipami, ['list', '-f', 'invalid=42'])

        assert r.exit_code == 2
        assert 'Invalid value' in r.output

    def test_list_filter_quiet(self, base_image, released_image):
        r = runner.invoke(shipami, ['list', '-q', '-f', 'release=1.0.0'])

        lines = r.output.splitlines()

        assert r.exit_code == 0
        assert len(lines) == 1
        assert released_image.id in lines[0]

    def test_show_unmanaged(self, base_image):
        r = runner.invoke(shipami, ['show', base_image.id])

        assert r.exit_code == 0

    def test_show_managed(self, released_image):
        r = runner.invoke(shipami, ['show', released_image.id])

        assert r.exit_code == 0

    def test_show_multiple(self, base_image, released_image):
        r = runner.invoke(shipami, ['show', base_image.id, released_image.id])

        assert r.exit_code == 0

    def test_show_inexistant_id(self):
        r = runner.invoke(shipami, ['show', 'ami-42424242'])

        assert r.exit_code == 1
        assert 'Error: The image id \'[ami-42424242]\' does not exist' in r.output

    def test_copy(self, ec2, base_image):
        image_number = len(ec2.meta.client.describe_images()['Images'])

        expected_tags = [
            {
                'Key': 'shipami:managed',
                'Value': 'True'
            },
            {
                'Key': 'shipami:copied_from',
                'Value': 'eu-west-1:{}'.format(base_image.id)
            }
        ]

        r = runner.invoke(shipami, ['copy', base_image.id])

        returned_image_id = r.output.strip()
        image = ec2.Image(returned_image_id)

        assert r.exit_code == 0
        assert len(ec2.meta.client.describe_images()['Images']) == image_number + 1
        assert image.name == base_image.name
        assert sorted(image.tags, key=lambda _: _['Key']) == sorted(expected_tags, key=lambda _: _['Key'])

    def test_copy_aliased(self, ec2, base_image):
        image_number = len(ec2.meta.client.describe_images()['Images'])

        expected_tags = [
            {
                'Key': 'shipami:managed',
                'Value': 'True'
            },
            {
                'Key': 'shipami:copied_from',
                'Value': 'eu-west-1:{}'.format(base_image.id)
            }
        ]

        r = runner.invoke(shipami, ['cp', base_image.id])

        returned_image_id = r.output.strip()
        image = ec2.Image(returned_image_id)

        assert r.exit_code == 0
        assert len(ec2.meta.client.describe_images()['Images']) == image_number + 1
        assert image.name == base_image.name
        assert sorted(image.tags, key=lambda _: _['Key']) == sorted(expected_tags, key=lambda _: _['Key'])

    def test_copy_wait(self, ec2, base_image):
        image_number = len(ec2.meta.client.describe_images()['Images'])

        expected_tags = [
            {
                'Key': 'shipami:managed',
                'Value': 'True'
            },
            {
                'Key': 'shipami:copied_from',
                'Value': 'eu-west-1:{}'.format(base_image.id)
            }
        ]

        r = runner.invoke(shipami, ['copy', base_image.id, '--wait'])

        returned_image_id = r.output.strip()
        image = ec2.Image(returned_image_id)

        assert r.exit_code == 0
        assert len(ec2.meta.client.describe_images()['Images']) == image_number + 1
        assert image.name == base_image.name
        assert sorted(image.tags, key=lambda _: _['Key']) == sorted(expected_tags, key=lambda _: _['Key'])

    def test_copy_invalid_name(self, base_image):
        NAME = 'aa'

        r = runner.invoke(shipami, ['copy', base_image.id, '--name', NAME])

        assert 'Error:' in r.output

    def test_copy_cleanup_name(self, ec2, base_image):
        NAME = 'foo#bar'

        r = runner.invoke(shipami, ['copy', base_image.id, '--name', NAME])

        returned_image_id = r.output.strip()
        image = ec2.Image(returned_image_id)

        assert r.exit_code == 0
        assert image.name == 'foo-bar'

    def test_copy_inexistant_id(self, ec2, base_image):
        r = runner.invoke(shipami, ['copy', 'ami-42424242'])

        assert r.exit_code == 1
        assert 'Error: The image id \'[ami-42424242]\' does not exist' in r.output

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

    def test_delete(self, ec2, copied_image):
        copied_image_id = copied_image.id
        r = runner.invoke(shipami, ['delete', copied_image_id])

        returned_image_id = r.output.strip()

        assert r.exit_code == 0
        assert len(ec2.meta.client.describe_images()['Images']) == 1
        assert returned_image_id == copied_image_id

    def test_delete_aliased(self, ec2, copied_image):
        copied_image_id = copied_image.id
        r = runner.invoke(shipami, ['rm', copied_image_id])

        returned_image_id = r.output.strip()

        assert r.exit_code == 0
        assert len(ec2.meta.client.describe_images()['Images']) == 1
        assert returned_image_id == copied_image_id

    def test_delete_not_managed(self, ec2, base_image):
        base_image_id = base_image.id
        r = runner.invoke(shipami, ['delete', base_image_id])

        assert r.exit_code == 1
        assert len(ec2.meta.client.describe_images()['Images']) == 1
        assert 'Error: {} is either a release or not managed by shipami'.format(base_image_id) in r.output

    def test_delete_released_image(self, ec2, released_image):
        released_image_id = released_image.id
        r = runner.invoke(shipami, ['delete', released_image_id])

        assert r.exit_code == 1
        assert len(ec2.meta.client.describe_images()['Images']) == 2
        assert 'Error: {} is either a release or not managed by shipami'.format(released_image_id) in r.output

    def test_delete_force(self, ec2, base_image):
        base_image_id = base_image.id
        r = runner.invoke(shipami, ['delete', '--force', base_image_id])

        returned_image_id = r.output.strip()

        assert r.exit_code == 0
        assert len(ec2.meta.client.describe_images()['Images']) == 0
        assert returned_image_id == base_image_id

    def test_delete_force_released(self, ec2, released_image):
        released_image_id = released_image.id
        r = runner.invoke(shipami, ['delete', '--force', released_image_id])

        returned_image_id = r.output.strip()

        assert r.exit_code == 0
        assert len(ec2.meta.client.describe_images()['Images']) == 1
        assert returned_image_id == released_image_id

    def test_delete_deleted_source(self, ec2, deleted_copied_image):
        deleted_copied_image_id = deleted_copied_image.id
        r = runner.invoke(shipami, ['delete', deleted_copied_image_id])

        print(r.output)

        returned_image_id = r.output.strip()

        assert r.exit_code == 0
        assert len(ec2.meta.client.describe_images()['Images']) == 0
        assert returned_image_id == deleted_copied_image_id

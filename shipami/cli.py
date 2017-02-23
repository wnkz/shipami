from . import __version__ as VERSION

import os
import sys
import subprocess
import json
import click
import boto3
import botocore

import botocore.vendored.requests.packages.urllib3 as urllib3
urllib3.disable_warnings(urllib3.exceptions.SecurityWarning)


class ShipAMI(object):

    MARKETPLACE_REGION = 'us-east-1'
    MARKETPLACE_ACCOUNT_ID = '679593333241'

    def __init__(self, region=None):
        self._region = region or boto3.session.Session().region_name
        self._session = boto3.session.Session(region_name=self._region)
        self._marketplace_session = boto3.session.Session(region_name=self.MARKETPLACE_REGION)

    def ship(self, image_id, share=True):
        ec2 = self._session.resource('ec2')

        source_image = ec2.Image(image_id)
        source_image.create_tags(
            Tags=[
                {
                    'Key': 'shipami:managed',
                    'Value': 'True'
                }
            ]
        )

        copied_image = self.__copy_image_to_marketplace(source_image, self._region)
        self.__wait_for_image(copied_image)
        self.__copy_tags(source_image, copied_image)
        if share:
            self.__share_image_with_marketplace(copied_image)

        source_image.create_tags(
            Tags=[
                {
                    'Key': 'shipami:copied_to',
                    'Value': '{}:{}'.format(self.MARKETPLACE_REGION, copied_image.id)
                }
            ]
        )

        copied_image.create_tags(
            Tags=[
                {
                    'Key': 'shipami:copied_from',
                    'Value': '{}:{}'.format(self._region, source_image.id)
                }
            ]
        )

    def delete(self, image_ids):
        ec2 = self._session.resource('ec2')

        for image_id in image_ids:
            image = ec2.Image(image_id)
            snapshots = self.__get_image_snapshots(image, ec2)

            click.echo('Deregistering {}'.format(image.id))
            image.deregister()
            for snapshot in snapshots:
                click.echo('  Deleting {}'.format(snapshot.id))
                snapshot.delete()

    def list(self):
        ec2 = self._session.resource('ec2')

        r = ec2.meta.client.describe_images(
            Owners=[
                'self'
            ]
        )

        images = r['Images']
        for image in images:
            click.echo('{} ({}) [{}]'.format(image['ImageId'], image['Name'], 'MANAGED' if self.__is_managed(image) else 'UNMANAGED'))

    def __share_image_with_marketplace(self, image):
        click.echo('Setting AWS Marketplace permissions to image {} ...'.format(image.id))

        image.modify_attribute(
            Attribute='launchPermission',
            OperationType='add',
            UserIds=[
                self.MARKETPLACE_ACCOUNT_ID
            ]
        )

        for snapshot in self.__get_image_snapshots(image):
            click.echo('  Setting AWS Marketplace permissions to snapshot {} ...'.format(snapshot.id))
            snapshot.modify_attribute(
                Attribute='createVolumePermission',
                OperationType='add',
                UserIds=[
                    self.MARKETPLACE_ACCOUNT_ID
                ]
            )

    def __copy_tags(self, src_image, dst_image):
        click.echo('Copying tags from image {} to image {} ...'.format(src_image.id, dst_image.id))

        dst_image.create_tags(Tags=src_image.tags)

        for snapshot in self.__get_image_snapshots(dst_image):
            click.echo('  Copying tags to snapshot {} ...'.format(snapshot.id))
            snapshot.create_tags(Tags=src_image.tags)

    def __wait_for_image(self, image):
        click.echo('Waiting for image {} to be available ...'.format(image.image_id))

        image.wait_until_exists(
            Filters=[
                {
                    'Name': 'state',
                    'Values': [
                        'available'
                    ]
                }
            ]
        )

    def __copy_image_to_marketplace(self, image, region):
        click.echo('Copying image {} from {} to {} ...'.format(image.image_id, region, self.MARKETPLACE_REGION))

        ec2 = self._marketplace_session.resource('ec2')
        r = ec2.meta.client.copy_image(
            SourceRegion=region,
            SourceImageId=image.id,
            Name=image.name,
            Description=image.description
        )

        return ec2.Image(r['ImageId'])

    def __is_managed(self, image):
        tags = image.get('Tags', [])
        for tag in tags:
            if tag.get('Key') == 'shipami:managed' and tag.get('Value') == 'True':
                return True
        return False

    def __is_ami_shared(self, image, ec2=None):
        for snapshot in self.__get_image_snapshots(image, ec2):
            if not self.__is_snapshot_shared(snapshot):
                return False
        return self.__is_image_shared(image)

    def __is_image_shared(self, image):
        r = image.describe_attribute(
            Attribute='launchPermission'
        )

        for permission in r['LaunchPermissions']:
            if permission['UserId'] == self.MARKETPLACE_ACCOUNT_ID:
                return True
        return False

    def __is_snapshot_shared(self, snapshot):
        r = snapshot.describe_attribute(
            Attribute='createVolumePermission'
        )

        for permission in r['CreateVolumePermissions']:
            if permission['UserId'] == self.MARKETPLACE_ACCOUNT_ID or permission['UserId'] == 'aws-marketplace':
                return True
        return False

    def __get_image_snapshots(self, image, ec2=None):
        ec2 = ec2 or self._marketplace_session.resource('ec2')
        snapshots = []

        for device in image.block_device_mappings:
            if 'Ebs' in device:
                snapshots.append(ec2.Snapshot(device['Ebs']['SnapshotId']))
        return snapshots


@click.group()
@click.version_option(VERSION)
@click.option('--region')
@click.pass_context
def cli(ctx, region):
    """CLI tool to manage AWS AMI and Marketplace"""
    ctx.obj = ShipAMI(region)


@cli.command()
@click.pass_obj
def list(shipami):
    shipami.list()


@cli.command()
@click.argument('image-id')
@click.option('--share/--no-share', default=True)
@click.pass_obj
def ship(shipami, image_id, share):
    shipami.ship(image_id, share)


@cli.command()
@click.argument('image-id', nargs=-1)
@click.pass_obj
def delete(shipami, image_id):
    shipami.delete(image_id)

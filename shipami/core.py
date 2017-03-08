import json
import logging
import click
import boto3
import botocore
import time

import botocore.vendored.requests.packages.urllib3 as urllib3
urllib3.disable_warnings(urllib3.exceptions.SecurityWarning)

logging.basicConfig()
logger = logging.getLogger(__name__)

class ShipAMI(object):

    MARKETPLACE_REGION = 'us-east-1'
    MARKETPLACE_ACCOUNT_ID = '679593333241'

    def __init__(self, region=None):
        self._region = region or boto3.session.Session().region_name
        self._session = boto3.session.Session(region_name=self._region)
        self._sessions = {}

    def __get_session(self, region=None):
        region = region or self._region
        session = self._sessions.get(region)
        if not session:
            self._sessions[region] = boto3.session.Session(region_name=region)
            session = self._sessions[region]
        return session

    def list(self):
        ec2 = self.__get_session().client('ec2')

        r = ec2.describe_images(
            Owners=[
                'self'
            ]
        )

        images = r['Images']
        managed_images = filter(lambda _: self.__is_managed(_), images)
        unmanaged_images = filter(lambda _: not self.__is_managed(_), images)

        for image in managed_images:
            image['ShipAMI:copied_from'] = self.__get_tag(image, 'shipami:copied_from')

        return {
            'managed': managed_images,
            'unmanaged': unmanaged_images
        }

    def delete(self, image_ids, force=False):
        ec2 = self.__get_session().resource('ec2')

        for image_id in image_ids:
            image = ec2.Image(image_id)

            if not self.__is_managed(image) and not force:
                logger.error('AMI [{}] is not managed by shipami'.format(image.id))
                raise click.Abort

            try:
                image.deregister(DryRun=True)
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'DryRunOperation':

                    # TODO: Refactor
                    copied_from = self.__get_tag(image, 'shipami:copied_from')
                    if copied_from:
                        from_region, from_image_id = copied_from.split(':')
                        from_image = self.__get_session(from_region).resource('ec2').Image(from_image_id)
                        copied_to = self.__get_tag(from_image, 'shipami:copied_to')
                        logger.info('Removing {} from {} shipami:copied_to tag'.format(image.id, from_image.id))
                        copied_to = copied_to.split(',')
                        copied_to = filter(lambda _: _.split(':')[1] != image.id, copied_to)
                        copied_to = ','.join(copied_to)
                        if copied_to:
                            self.__set_tag(from_image, 'shipami:copied_to', copied_to)
                        else:
                            self.__delete_tag(from_image, 'shipami:copied_to')
                    #

                    logger.info('Deregistering {}'.format(image.id))
                    snapshots = self.__get_image_snapshots(image)
                    image.deregister()
                    for snapshot in snapshots:
                        logger.info('Deleting {}'.format(snapshot.id))
                        snapshot.delete()
                else:
                    logger.error('Cannot delete AMI [{}]'.format(image.id))
                    raise click.Abort

    def release(self, image_id, release, name=None, description=None, source_region=None, copy_tags=True, copy_tags_to_snapshots=False, copy_permissions=False, wait=False):
        src_image = self.__get_session(source_region).resource('ec2').Image(image_id)
        rls_image = self.__copy_image(src_image, name=name, description=description, copy_tags=copy_tags, copy_tags_to_snapshots=copy_tags_to_snapshots, wait=wait)
        self.__set_tag(rls_image, 'shipami:release', release)
        return rls_image.id

    def share(self, image_id, account_id=None, remove=False):
        image = self.__get_session().resource('ec2').Image(image_id)
        account_id = account_id or self.MARKETPLACE_ACCOUNT_ID
        operation = 'add' if not remove else 'remove'
        operation_log = 'Adding' if not remove else 'Removing'

        logger.info('{} permissions for {} on image {} ...'.format(operation_log, account_id, image.id))
        self.__wait_for_image(image)
        self.__share_modify_attribute(image, 'launchPermission', operation, account_id)
        for snapshot in self.__get_image_snapshots(image):
            logger.info('{} permissions for {} on snapshot {} ...'.format(operation_log, account_id, snapshot.id))
            self.__wait_for_snapshot(snapshot)
            self.__share_modify_attribute(snapshot, 'createVolumePermission', operation, account_id)

    def __share_modify_attribute(self, obj, attribute, operation, account_id):
        obj.modify_attribute(
            Attribute=attribute,
            OperationType=operation,
            UserIds=[
                account_id
            ]
        )

    def __copy_image(self, src_image, name=None, description=None, copy_tags=True, copy_tags_to_snapshots=False, wait=False):
        name = name or src_image.name
        description = description or src_image.description
        src_region = src_image.meta.client.meta.region_name

        logger.info('Copying image {} from {} to {} ...'.format(src_image.id, src_region, self._region))

        r = self.__get_session().client('ec2').copy_image(
            SourceRegion=src_region,
            SourceImageId=src_image.id,
            Name=name,
            Description=description
        )

        dst_image = self.__get_session().resource('ec2').Image(r['ImageId'])
        self.__append_tag(src_image, 'shipami:copied_to', '{}:{}'.format(self._region, dst_image.id))
        self.__set_managed(dst_image)
        self.__set_tag(dst_image, 'shipami:copied_from', '{}:{}'.format(src_region, src_image.id))

        if copy_tags:
            self.__copy_tags(src_image, dst_image, copy_tags_to_snapshots)
            # removes irrelevant 'copied_to' tag
            # TODO: Find a way to filter tags properly when copying
            self.__delete_tag(dst_image, 'shipami:copied_to')

        if wait:
            self.__wait_for_image(dst_image)

        return dst_image

    def __copy_tags(self, src_image, dst_image, copy_to_snapshots=False):
        logger.info('Copying tags from image {} to image {} ...'.format(src_image.id, dst_image.id))

        dst_image.create_tags(Tags=src_image.tags)
        if copy_to_snapshots:
            for snapshot in self.__get_image_snapshots(dst_image):
                logger.info('  Copying tags to snapshot {} ...'.format(snapshot.id))
                snapshot.create_tags(Tags=src_image.tags)

    def __set_managed(self, image):
        image.create_tags(
            Tags=[
                {
                    'Key': 'shipami:managed',
                    'Value': 'True'
                }
            ]
        )

    def __append_tag(self, obj, key, value):
        p_value = self.__get_tag(obj, key)
        if p_value:
            value = ','.join([p_value, value])

        self.__set_tag(obj, key, value)

    def __get_tag(self, obj, key):
        tags = obj.get('Tags', []) if type(obj) is dict else obj.tags

        for tag in tags:
            if tag.get('Key') == key:
                return tag.get('Value')
        return None

    def __set_tag(self, obj, key, value):
        obj.create_tags(
            Tags=[
                {
                    'Key': key,
                    'Value': value
                }
            ]
        )

    def __delete_tag(self, obj, key):
        obj.meta.client.delete_tags(
            Resources=[
                obj.id
            ],
            Tags=[
                {
                    'Key': key
                }
            ]
        )

    def __is_managed(self, image):
        if self.__get_tag(image, 'shipami:managed'):
            return True
        return False

    # DEPRECATED
    def __is_ami_shared(self, image, ec2=None):
        for snapshot in self.__get_image_snapshots(image, ec2):
            if not self.__is_snapshot_shared(snapshot):
                return False
        return self.__is_image_shared(image)

    # DEPRECATED
    def __is_image_shared(self, image):
        r = image.describe_attribute(
            Attribute='launchPermission'
        )

        for permission in r['LaunchPermissions']:
            if permission['UserId'] == self.MARKETPLACE_ACCOUNT_ID:
                return True
        return False

    # DEPRECATED
    def __is_snapshot_shared(self, snapshot):
        r = snapshot.describe_attribute(
            Attribute='createVolumePermission'
        )

        for permission in r['CreateVolumePermissions']:
            if permission['UserId'] == self.MARKETPLACE_ACCOUNT_ID or permission['UserId'] == 'aws-marketplace':
                return True
        return False

    def __get_image_snapshots(self, image):
        region_name = image.meta.client.meta.region_name
        ec2 = self.__get_session(region_name).resource('ec2')
        snapshots = []

        # We must wait for the image to be avaiale in order to get the SnapshotIds
        self.__wait_for_image(image)
        for block_device_mapping in image.block_device_mappings:
            if block_device_mapping.get('Ebs'):
                snapshots.append(ec2.Snapshot(block_device_mapping['Ebs']['SnapshotId']))
        return snapshots

    def __wait_for_image(self, image, state='available'):
        logger.debug('Waiting for image {} to be {} ...'.format(image.id, state))
        image.wait_until_exists(
            Filters=[
                {
                    'Name': 'state',
                    'Values': [
                        state
                    ]
                }
            ]
        )

    def __wait_for_snapshot(self, snapshot):
        logger.debug('Waiting for snapshot {} to be ready ...'.format(snapshot.id))
        snapshot.wait_until_completed(
            Filters=[
                {
                    'Name': 'status',
                    'Values': [
                        'completed',
                        'error'
                    ]
                }
            ]
        )

    def __wait_for_block_devices(self, image):
        logger.debug('Waiting for block devices ...')
        while not image.block_device_mappings:
            image.reload()
            time.sleep(1)

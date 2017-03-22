import json
import logging
import click
import boto3
import botocore
import time

import botocore.vendored.requests.packages.urllib3 as urllib3
urllib3.disable_warnings(urllib3.exceptions.SecurityWarning)

logging.basicConfig()
logger = logging.getLogger('shipami.cli')


class ShipAMI(object):

    MARKETPLACE_REGION = 'us-east-1'
    MARKETPLACE_ACCOUNT_ID = '679593333241'

    def __init__(self, region=None):
        self._region = region or boto3.session.Session().region_name
        self._sessions = {}

    def __get_session(self, region=None):
        region = region or self._region
        session = self._sessions.get(region)
        if not session:
            self._sessions[region] = boto3.session.Session(region_name=region)
            session = self._sessions[region]
        return session

    def validate_ami_name(self, name, clean=False):
        allowed = ['(', ')', '[', ']', ' ', '.', '/', '-', '\'', '@', '_']

        if len(name) < 3 or len(name) > 128:
            raise click.BadParameter('AMI Name must be 3-128 long (got: "{}")'.format(name))

        if clean:
            return ''.join(map(lambda _: _ if _.isalnum() or _ in allowed else '-', name))
        return name

    def list(self):
        ec2 = self.__get_session().client('ec2')

        r = ec2.describe_images(
            Owners=[
                'self'
            ]
        )

        images = r['Images']
        images = sorted(images, key=lambda _: _['CreationDate'], reverse=True)
        managed_images = list(filter(lambda _: self.__is_managed(_), images))
        unmanaged_images = list(filter(lambda _: not self.__is_managed(_), images))

        for image in managed_images:
            image['shipami:copied_from'] = self.__get_tag(image, 'shipami:copied_from')

        for image in unmanaged_images:
            image['shipami:copied_to'] = self.__get_tag(image, 'shipami:copied_to')

        return {
            'managed': managed_images,
            'unmanaged': unmanaged_images
        }

    def show(self, image_id):
        ec2 = self.__get_session().client('ec2')
        image = self.__get_session().resource('ec2').Image(image_id)

        r = ec2.describe_images(
            Owners=[
                'self'
            ],
            ImageIds=[
                image_id
            ]
        )

        r['Images'][0]['Shares'] = self.__get_image_permissions(image)
        for share in r['Images'][0]['Shares']:
            if share.get('UserId') == self.MARKETPLACE_ACCOUNT_ID:
                share['Marketplace'] = self.__is_ami_shared(image)

        return r['Images'][0]

    def copy(self, image_id, **kwargs):
        src_image = self.__get_session(kwargs.pop('source_region')).resource('ec2').Image(image_id)
        dst_image = self.__copy_image(src_image, **kwargs)
        return dst_image.id

    def release(self, image_id, release, **kwargs):
        image = self.__get_session().resource('ec2').Image(self.copy(image_id, name_suffix=release, **kwargs))
        self.__set_tag(image, 'shipami:release', release)
        return image.id

    def share(self, image_id, account_id=None, remove=False):
        image = self.__get_session().resource('ec2').Image(image_id)
        account_id = account_id or self.MARKETPLACE_ACCOUNT_ID
        operation = 'add' if not remove else 'remove'
        operation_log = 'adding' if not remove else 'removing'

        logger.debug('{} permissions for {} on image {}'.format(operation_log, account_id, image.id))
        self.__wait_for_image(image)
        self.__share_modify_attribute(image, 'launchPermission', operation, account_id)
        for snapshot in self.__get_image_snapshots(image):
            logger.debug('{} permissions for {} on snapshot {}'.format(operation_log, account_id, snapshot.id))
            self.__wait_for_snapshot(snapshot)
            self.__share_modify_attribute(snapshot, 'createVolumePermission', operation, account_id)

    def delete(self, image_ids, force=False):
        ec2 = self.__get_session().resource('ec2')
        deleted = []

        for image_id in image_ids:
            image = ec2.Image(image_id)

            managed = self.__is_managed(image)
            if not managed:
                if not force:
                    logger.error('AMI [{}] is not managed by shipami'.format(image.id))
                    raise click.Abort
            else:
                copied_from = self.__get_tag(image, 'shipami:copied_from')
                if copied_from:
                    from_image = self.__get_copied_from_image(copied_from)
                    remove_copied_to = self.__generate_copy_tag(image)

            try:
                snapshots = self.__get_image_snapshots(image)
                logger.debug('deregistering {}'.format(image.id))
                image.deregister()
                for snapshot in snapshots:
                    logger.debug('deleting {}'.format(snapshot.id))
                    snapshot.delete()
            except botocore.exceptions.ClientError as e:
                logger.error(e)
                raise click.Abort

            if managed and copied_from:
                self.__remove_copied_to(from_image, remove_copied_to)

            deleted.append(image_id)
        return deleted

    def __copy_image(self, src_image, name=None, name_suffix=None, description=None, copy_tags=True, copy_tags_to_snapshots=False, copy_permissions=False, wait=False):
        name = name or src_image.name
        if name_suffix:
            name = '-'.join([name, name_suffix])
        name = self.validate_ami_name(name, clean=True)
        description = description or src_image.description
        src_region = src_image.meta.client.meta.region_name

        logger.debug('copying image {} from {} to {}'.format(src_image.id, src_region, self._region))
        try:
            r = self.__get_session().client('ec2').copy_image(
                SourceRegion=src_region,
                SourceImageId=src_image.id,
                Name=name,
                Description=description
            )
        except botocore.exceptions.ClientError as e:
            logger.error(e)
            raise click.Abort

        dst_image = self.__get_session().resource('ec2').Image(r['ImageId'])
        self.__append_tag(src_image, 'shipami:copied_to', '{}:{}'.format(self._region, dst_image.id))

        if copy_tags:
            self.__copy_tags(src_image, dst_image, copy_tags_to_snapshots)
            # removes irrelevant 'copied_to' tag
            # TODO: Find a way to filter tags properly when copying
            self.__delete_tag(dst_image, 'shipami:copied_to')

        self.__set_managed(dst_image)
        self.__set_tag(dst_image, 'shipami:copied_from', '{}:{}'.format(src_region, src_image.id))

        # TODO: implement copy_permissions

        if wait:
            self.__wait_for_image(dst_image)

        return dst_image

    def __copy_tags(self, src_image, dst_image, copy_to_snapshots=False):
        logger.debug('copying tags from image {} to image {}'.format(src_image.id, dst_image.id))

        dst_image.create_tags(Tags=src_image.tags)
        if copy_to_snapshots:
            for snapshot in self.__get_image_snapshots(dst_image):
                logger.debug('copying tags to snapshot {}'.format(snapshot.id))
                snapshot.create_tags(Tags=src_image.tags)

    def __share_modify_attribute(self, obj, attribute, operation, account_id):
        obj.modify_attribute(
            Attribute=attribute,
            OperationType=operation,
            UserIds=[
                account_id
            ]
        )

    def __get_copied_from_image(self, copied_from):
        region, image_id = copied_from.split(':')
        image = self.__get_session(region).resource('ec2').Image(image_id)
        return image

    def __generate_copy_tag(self, image):
        return '{}:{}'.format(self.__get_image_region(image), image.id)

    def __remove_copied_to(self, image, to_remove):
        copied_to = self.__get_tag(image, 'shipami:copied_to')
        logger.debug('removing "{}" from {} shipami:copied_to tag'.format(to_remove, image.id))
        logger.debug('shipami:copied_to: {}'.format(copied_to))

        copied_to = copied_to.split(',')
        copied_to = filter(lambda _: _ != to_remove, copied_to)
        copied_to = ','.join(copied_to)

        if copied_to:
            logger.debug('set shipami:copied_to: {}'.format(copied_to))
            self.__set_tag(image, 'shipami:copied_to', copied_to)
        else:
            logger.debug('removed shipami:copied_to')
            self.__delete_tag(image, 'shipami:copied_to')

    def __get_image_region(self, image):
        return image.meta.client.meta.region_name

    def __get_image_snapshots(self, image):
        region_name = self.__get_image_region(image)
        ec2 = self.__get_session(region_name).resource('ec2')
        snapshots = []

        # We must wait for the image to be avaiale in order to get the SnapshotIds
        self.__wait_for_image(image)
        for block_device_mapping in image.block_device_mappings:
            if block_device_mapping.get('Ebs'):
                snapshots.append(ec2.Snapshot(block_device_mapping['Ebs']['SnapshotId']))
        return snapshots

    def __set_managed(self, image):
        self.__set_tag(image, 'shipami:managed', 'True')

    def __append_tag(self, obj, key, value):
        p_value = self.__get_tag(obj, key)
        if p_value:
            value = ','.join([p_value, value])

        self.__set_tag(obj, key, value)

    def __get_tag(self, obj, key):
        try:
            tags = obj.tags or []
        except AttributeError:
            try:
                tags = obj.get('Tags', [])
            except AttributeError:
                return None

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
        if self.__get_tag(image, 'shipami:managed') == 'True':
            return True
        return False

    def __get_image_permissions(self, image):
        r = image.describe_attribute(
            Attribute='launchPermission'
        )

        return r['LaunchPermissions']

    def __get_snapshot_permissions(self, snapshot):
        r = snapshot.describe_attribute(
            Attribute='createVolumePermission'
        )

        return r['CreateVolumePermissions']

    def __is_ami_shared(self, image, account_id=None):
        account_id = account_id or self.MARKETPLACE_ACCOUNT_ID

        for snapshot in self.__get_image_snapshots(image):
            if not self.__is_snapshot_shared(snapshot, account_id):
                return False
        return self.__is_image_shared(image, account_id)

    def __is_image_shared(self, image, account_id=None):
        account_id = account_id or self.MARKETPLACE_ACCOUNT_ID

        for permission in self.__get_image_permissions(image):
            if (permission.get('UserId') == account_id) or (account_id == self.MARKETPLACE_ACCOUNT_ID and permission.get('UserId') == 'aws-marketplace'):
                return True

    def __is_snapshot_shared(self, snapshot, account_id=None):
        account_id = account_id or self.MARKETPLACE_ACCOUNT_ID

        for permission in self.__get_snapshot_permissions(snapshot):
            if (permission.get('UserId') == account_id) or (account_id == self.MARKETPLACE_ACCOUNT_ID and permission.get('UserId') == 'aws-marketplace'):
                return True
        return False

    def __wait_for_image(self, image, state='available'):
        logger.debug('waiting for image {} to be {}'.format(image.id, state))
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
        image.reload()

    def __wait_for_snapshot(self, snapshot):
        logger.debug('waiting for snapshot {} to be ready'.format(snapshot.id))
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
        snapshot.reload()

    def __wait_for_block_devices(self, image):
        logger.debug('waiting for block devices')
        while not image.block_device_mappings:
            image.reload()
            time.sleep(1)

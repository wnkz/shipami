from . import __version__ as VERSION

import json
import logging
import click

from shipami.core import ShipAMI

logging.basicConfig()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(VERSION)
@click.option('--region')
@click.option('-v', '--verbose', is_flag=True, default=False)
@click.pass_context
def cli(ctx, region, verbose):
    """CLI tool to manage AWS AMI and Marketplace"""
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    ctx.obj = ShipAMI(region)


@cli.command()
@click.pass_obj
def list(shipami):
    r = shipami.list()

    state_colors = {
        'available': 'green',
        'pending': 'yellow',
        'failed': 'red'
    }

    if r['managed']:
        click.echo('Managed images:')
        click.echo()
        for image in r['managed']:
            click.secho('\t{}:\t{} [{}] (from: {})'.format(
                    image['ImageId'],
                    image['Name'],
                    image['State'],
                    image['shipami:copied_from'] or 'unknown'
                ),
                fg=state_colors[image['State']]
            )

    if r['managed'] and r['unmanaged']:
        click.echo()

    if r['unmanaged']:
        click.echo('Unmanaged images:')
        click.echo()
        for image in r['unmanaged']:
            click.echo('\t{}:\t{}'.format(image['ImageId'], image['Name']), nl=False)
            if image['shipami:copied_to']:
                click.secho(' (to: {})'.format(image['shipami:copied_to']), nl=False, fg='blue')
            click.echo()

@cli.command()
@click.argument('image-id')
@click.pass_obj
def show(shipami, image_id):
    image = shipami.show(image_id)
    click.echo('{} ({}) [{}]'.format(image['ImageId'], image['Name'], image['State']))

    if image.get('Tags'):
        click.echo('tags:')
        for tag in sorted(image['Tags'], key=lambda _: _['Key'], reverse=True):
            key = tag.get('Key')
            value = tag.get('Value')
            if 'shipami:' in key:
                color = 'blue'
            else:
                color = 'white'
            click.echo('  {}: {}'.format(key, click.style(value, fg=color, bold=True)))

    click.echo('devices mappings:')
    for block_device_mapping in image['BlockDeviceMappings']:
        click.echo('  {} {}Go type:{}'.format(
                block_device_mapping['DeviceName'],
                block_device_mapping['Ebs']['VolumeSize'],
                block_device_mapping['Ebs']['VolumeType']
            )
        )
    if image.get('Shares'):
        click.echo('shared with:')
        for share in image.get('Shares'):
            click.echo('  {}'.format(share['UserId']), nl=False)
            if share.get('Marketplace') is not None:
                click.echo(' (AWS MARKETPLACE)', nl=False)
                if share.get('Marketplace') is True:
                    click.secho(' OK', fg='green', nl=False)
                else:
                    click.secho(' PARTIAL', fg='yellow', nl=False)
            click.echo()


@cli.command()
@click.argument('image-id')
@click.option('--name')
@click.option('--description')
@click.option('--source-region')
@click.option('--copy-tags/--no-copy-tags', default=True)
@click.option('--copy-tags-to-snapshots/--no-copy-tags-to-snapshots', default=False)
@click.option('--copy-permissions/--no-copy-permissions', default=False)
@click.option('--wait/--no-wait', default=False)
@click.pass_obj
def copy(shipami, **kwargs):
    image_id = shipami.copy(kwargs.pop('image_id'), **kwargs)
    click.echo(image_id)


@cli.command()
@click.argument('image-id')
@click.argument('release')
@click.option('--name')
@click.option('--description')
@click.option('--source-region')
@click.option('--copy-tags/--no-copy-tags', default=True)
@click.option('--copy-tags-to-snapshots/--no-copy-tags-to-snapshots', default=False)
@click.option('--copy-permissions/--no-copy-permissions', default=False)
@click.option('--wait/--no-wait', default=False)
@click.pass_obj
def release(shipami, **kwargs):
    image_id = shipami.release(kwargs.pop('image_id'), kwargs.pop('release'), **kwargs)
    click.echo(image_id)


@cli.command()
@click.argument('image-id')
@click.option('--account-id')
@click.option('--remove', is_flag=True, default=False)
@click.pass_obj
def share(shipami, **kwargs):
    shipami.share(kwargs.pop('image_id'), **kwargs)


@cli.command()
@click.argument('image-id', nargs=-1)
@click.option('--force', '-f', is_flag=True, default=False)
@click.pass_obj
def delete(shipami, image_id, force):
    for deleted in shipami.delete(image_id, force):
        click.echo(deleted)

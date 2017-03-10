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

    click.echo('Managed images:\n')
    for image in r['managed']:
        click.secho('\t{}:\t{} [{}] (Copied from: {})'.format(image['ImageId'], image['Name'], image['State'], image['ShipAMI:copied_from']), fg=state_colors[image['State']])
    click.echo()
    click.echo('Unmanaged images:\n')
    for image in r['unmanaged']:
        click.echo('\t{}:\t{}'.format(image['ImageId'], image['Name']))


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
@click.option('--force', is_flag=True, default=False)
@click.pass_obj
def delete(shipami, image_id, force):
    for deleted in shipami.delete(image_id, force):
        click.echo(deleted)

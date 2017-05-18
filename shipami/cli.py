from . import __version__ as VERSION

import json
import logging
import click

from tabulate import tabulate
import datetime, timeago, dateutil.parser

from shipami.core import ShipAMI

logging.basicConfig()
logger = logging.getLogger(__name__)

state_colors = {
    'available': 'green',
    'pending': 'yellow',
    'failed': 'red'
}

def validate_filter(ctx, param, filters):
    validated_filters = []
    for f in filters:
        try:
            k, v = f.split('=')
            validated_filters.append((k, v))
        except ValueError:
            raise click.BadParameter('filter must be in format "key=value"')
    return tuple(validated_filters)

class AliasedGroup(click.Group):
    ALIASES = {
        'ls': 'list',
        'cp': 'copy',
        'rm': 'delete'
    }

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        if self.ALIASES.get(cmd_name, None):
            return click.Group.get_command(self, ctx, self.ALIASES[cmd_name])
        return None

@click.group(cls=AliasedGroup)
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
@click.option('--quiet', '-q', is_flag=True)
@click.option('filter_', '--filter', '-f', multiple=True, callback=validate_filter)
@click.option('--color/--no-color', default=True)
@click.pass_obj
def list(shipami, filter_, quiet, color):
    headers = ['NAME', 'RELEASE', 'ID', 'STATE', 'CREATED', 'MANAGED', 'COPIED FROM', 'COPIED TO']
    headers_mapping = {
        'NAME': 'Name',
        'RELEASE': 'Release',
        'ID': 'ImageId',
        'STATE': 'State',
        'CREATED': 'CreationDate',
        'MANAGED': 'Managed',
        'COPIED FROM': 'CopiedFrom',
        'COPIED TO': 'CopiedTo'
    }

    filters = ['NAME', 'RELEASE', 'ID', 'STATE', 'MANAGED']
    filters_mapping = {}
    for f in filters:
        filters_mapping[f.strip().lower()] = f

    for k, v in filter_:
        if k not in filters_mapping.keys():
            raise click.BadParameter('available filters are {}'.format(filters_mapping.keys()))

    def makefilter(k, v, attr):
        def f(_):
            x = _.get(attr)
            if x is None:
                return False
            if isinstance(x, bool):
                bool_mapping = {'yes': True, 'no': False}
                return x is bool_mapping.get(v)
            return v in x
        return f

    now = datetime.datetime.utcnow()
    try:
        images = shipami.list()
    except RuntimeError as e:
        raise click.ClickException(str(e))

    for k, v in filter_:
        attr = headers_mapping.get(filters_mapping.get(k))
        images = filter(makefilter(k, v, attr), images)

    images = sorted(images, key=lambda _: _['CreationDate'], reverse=True)

    if quiet:
        for image in images: click.echo(image.get('ImageId'))
    else:
        d = []
        for image in images:
            row = []
            for col in headers:
                value = image.get(headers_mapping.get(col))
                if col is 'STATE':
                    if color:
                        value = click.style(value, fg=state_colors.get(value))
                if col is 'CREATED':
                    value = timeago.format(dateutil.parser.parse(value, ignoretz=True), now)
                if col is 'MANAGED':
                    value = 'yes' if value else 'no'
                    if color and value is 'yes':
                        value = click.style(value, fg='white', bold=True)
                if col is 'COPIED TO':
                    if value and color:
                        value = click.style(value, fg='blue')
                if col is 'COPIED FROM':
                    if value and color:
                        value = click.style(value, fg='blue')
                    if value is None and image.get(headers_mapping.get('MANAGED')) is False:
                        value = 'origin'
                row.append(value)
            d.append(row)
        if d: print(tabulate(d, headers=headers, tablefmt='plain'))


@cli.command()
@click.argument('image-id', nargs=-1)
@click.pass_obj
def show(shipami, image_id):
    try:
        images = shipami.show(image_id)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    for i, image in enumerate(images):
        click.echo('id:\t{}'.format(image.get('ImageId')))
        click.echo('name:\t{}'.format(image.get('Name')))
        click.echo('state:\t{}'.format(click.style(image.get('State'), fg=state_colors.get(image.get('State')))))

        if image.get('Tags'):
            click.echo('tags:')
            for tag in sorted(image['Tags'], key=lambda _: _['Key']):
                key = tag.get('Key')
                value = tag.get('Value')
                color = 'blue' if 'shipami:' in key else 'white'
                click.echo('  {}: {}'.format(key, click.style(value, fg=color, bold=True)))

        if image.get('BlockDeviceMappings'):
            click.echo('devices mappings:')
            for block_device_mapping in image.get('BlockDeviceMappings', []):
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

        if i < len(images) - 1:
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
    try:
        image_id = shipami.copy(kwargs.pop('image_id'), **kwargs)
    except RuntimeError as e:
        raise click.ClickException(str(e))

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
    try:
        image_id = shipami.release(kwargs.pop('image_id'), kwargs.pop('release'), **kwargs)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    click.echo(image_id)


@cli.command()
@click.argument('image-id')
@click.option('--account-id')
@click.option('--remove', is_flag=True, default=False)
@click.pass_obj
def share(shipami, **kwargs):
    try:
        shipami.share(kwargs.pop('image_id'), **kwargs)
    except RuntimeError as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument('image-id', nargs=-1)
@click.option('--force', '-f', is_flag=True, default=False)
@click.pass_obj
def delete(shipami, image_id, force):
    try:
        deleted = shipami.delete(image_id, force)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    for d in deleted:
        click.echo(d)

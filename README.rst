====================================
ShipAMI - Simple AWS AMIs management
====================================

|Build Status| |Version| |Coverage| |License|

CLI for simple AWS AMIs management


.. |Build Status| image:: https://img.shields.io/travis/wnkz/shipami/master.svg?style=flat
    :target: https://travis-ci.org/wnkz/shipami
    :alt: Build Status

.. |Version| image:: https://img.shields.io/pypi/v/shipami.svg?style=flat
    :target: https://pypi.python.org/pypi/shipami/
    :alt: Version

.. |Coverage| image:: https://coveralls.io/repos/github/wnkz/shipami/badge.svg
    :target: https://coveralls.io/github/wnkz/shipami
    :alt: Coverage

.. |License| image:: https://img.shields.io/pypi/l/shipami.svg?style=flat
    :target: https://github.com/wnkz/shipami/blob/master/LICENSE
    :alt: License

Quick Start
===========

Install with ``pip``:

.. code-block:: sh

    $ pip install shipami
    $ shipami --help

Example: Publish AMI for AWS Marketplace
----------------------------------------

1. List available AMIs in your default region (eg. eu-west-1)

.. code-block:: sh

  $ shipami list
  NAME       RELEASE    ID            STATE      CREATED      MANAGED    COPIED FROM             COPIED TO
  foo                   ami-00000000  available  5 days ago   no         origin

2. Create a release based on this image in us-east-1 region

.. code-block:: sh

  $ shipami --region us-east-1 release ami-00000000 1.0 --source-region eu-west-1
  ami-000000aa

  $ shipami --region us-east-1 list
  NAME       RELEASE    ID            STATE      CREATED      MANAGED    COPIED FROM             COPIED TO
  foo-1.0    1.0        ami-000000aa  pending    just now     yes        eu-west-1:ami-00000000

3. Manually share with AWS Marketplace account

.. code-block:: sh

  $ shipami --region us-east-1 share ami-000000aa

  $ shipami --region us-east-1 show ami-000000aa
  id:     ami-000000aa
  name:   foo-1.0
  state:  available
  tags:
    shipami:copied_from: eu-west-1:ami-00000000
    shipami:managed: True
    shipami:release: 1.0
  devices mappings:
    /dev/xvda 8Go type:gp2
  shared with:
    679593333241 (AWS MARKETPLACE) OK

Commands
========

You can get further help and usage instructions on any command with the ``--help`` option.

``copy``
--------

.. code-block:: sh

  $ shipami copy ami-00000000
  ami-000000aa
  $ shipami list
  NAME       RELEASE    ID            STATE      CREATED      MANAGED    COPIED FROM             COPIED TO
  foo                   ami-00000000  available  5 days ago   no         origin                  eu-west-1:ami-000000aa
  foo                   ami-000000aa  pending    just now     yes        eu-west-1:ami-00000000


``delete``
----------

.. code-block:: sh

  $ shipami list
  NAME       RELEASE    ID            STATE      CREATED      MANAGED    COPIED FROM             COPIED TO
  foo                   ami-00000000  available  5 days ago   no         origin                  eu-west-1:ami-000000aa
  foo                   ami-000000aa  available  1 day ago    yes        eu-west-1:ami-00000000

  $ shipami delete ami-000000aa
  ami-000000aa

  $ shipami list
  NAME       RELEASE    ID            STATE      CREATED      MANAGED    COPIED FROM             COPIED TO
  foo                   ami-00000000  available  5 days ago   no         origin


``list``
--------

.. code-block:: sh

  $ shipami list
  NAME       RELEASE    ID            STATE      CREATED      MANAGED    COPIED FROM             COPIED TO
  foo                   ami-00000000  available  5 days ago   no         origin


``release``
-----------

.. code-block:: sh

  $ shipami release ami-00000000 1.0
  ami-000000aa
  $ shipami list
  NAME       RELEASE    ID            STATE      CREATED      MANAGED    COPIED FROM             COPIED TO
  foo                   ami-00000000  available  5 days ago   no         origin                  eu-west-1:ami-000000aa
  foo-1.0    1.0        ami-000000aa  pending    just now     yes        eu-west-1:ami-00000000


``share``
---------

.. code-block:: sh

  $ shipami share ami-000000aa 012345678912


``show``
--------

.. code-block:: sh

  $ shipami show ami-000000aa
  id:     ami-000000aa
  name:   foo-1.0
  state:  available
  tags:
    shipami:copied_from: eu-west-1:ami-00000000
    shipami:managed: True
    shipami:release: 1.0
  devices mappings:
    /dev/xvda 8Go type:gp2
  shared with:
    012345678912

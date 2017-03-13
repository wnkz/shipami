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

Publish AMI for AWS Marketplace
-------------------------------

.. code-block:: sh

  $ shipami --region us-east-1 release ami-00000000 1.0 --source-region eu-west-1
  ami-000000aa

  $ shipami --region us-east-1 list
  Managed images:

    ami-000000aa: foo-1.0 [pending] (from: eu-west-1:ami-00000000)

  $ shipami --region us-east-1 show ami-000000aa
  ami-000000aa (foo-1.0) [pending]
  tags:
    shipami:release: 1.0
    shipami:managed: True
    shipami:copied_from: eu-west-1:ami-00000000
  devices mappings:
    /dev/xvda 8Go type:gp2

  $ shipami --region us-east-1 share ami-000000aa

  $ shipami --region us-east-1 show ami-000000aa
  ami-000000aa (foo-1.0) [available]
  tags:
    shipami:release: 1.0
    shipami:managed: True
    shipami:copied_from: eu-west-1:ami-00000000
  devices mappings:
    /dev/xvda 8Go type:gp2
  shared with:
    679593333241 (AWS MARKETPLACE) OK

Commands
========

.. note::

   In the examples, we consider you have the following:
    - AWS credentials correctly configured and sufficient permissions
    - A base AMI with the ID ``ami-00000000`` and NAME ``foo``


``copy``
--------

.. code-block:: sh

  $ shipami copy ami-00000000
  ami-000000aa
  $ shipami list
  Managed images:

    ami-000000aa: foo [pending] (from: eu-west-1:ami-00000000)

  Unmanaged images:

    ami-00000000: foo (to: eu-west-1:ami-000000aa)


``delete``
----------


``list``
--------

.. code-block:: sh

  $ shipami list
  Unmanaged images:

  	ami-00000000:	foo


``release``
-----------

.. code-block:: sh

  $ shipami release ami-00000000 1.0
  ami-000000aa
  $ shipami list
  Managed images:

    ami-000000aa: foo-1.0 [pending] (from: eu-west-1:ami-00000000)

  Unmanaged images:

    ami-00000000: foo (to: eu-west-1:ami-000000aa)


``share``
---------


``show``
--------

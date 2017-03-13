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
-----------

Install with ``pip``:

.. code-block:: sh

    $ pip install shipami
    $ shipami --help


Commands
--------

.. note::

   In the examples, we consider you have the following:
    - AWS credentials correctly configured and sufficient permissions
    - A base AMI with the ID ``ami-00000000`` and NAME ``foo``


* ``list``

.. code-block:: sh

  $ shipami list
  Managed images:


  Unmanaged images:

  	ami-00000000:	foo


* ``copy``

.. code-block:: sh

  $ shipami copy ami-00000000
  ami-000000aa
  $ shipami list
  Managed images:

    ami-000000aa:	foo [pending] (from: eu-west-1:ami-00000000)

  Unmanaged images:

  	ami-00000000:	foo (to: eu-west-1:ami-000000aa)

#!/usr/bin/env python3
# Copyright (c) 2015-2016 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://www.opensource.org/licenses/mit-license.php .

"""
This module contains utilities for doing coverage analysis on the RPC
interface.

It provides a way to track which RPC commands are exercised during
testing.

"""
import os
import logging
import asyncio
import time

REFERENCE_FILENAME = 'rpc_interface.txt'

log = logging.getLogger("Scheduler")






async def acquire_cores_lambda(reader, writer, number_cores, rpc):
    message = str(number_cores) + ",A," + rpc
    writer.write(message.encode())
    await writer.drain()
    await reader.read(100)
    writer.close()

async def relinquish_cores_lambda(reader, writer, number_cores):
    message = str(number_cores) + ",R"
    writer.write(message.encode())
    await writer.drain()
    data = await reader.read(1)
    message = data.decode()
    writer.close()


def acquire_cores(number_cores, rpc):
    evloop = asyncio.new_event_loop()
    try:
        reader, writer = evloop.run_until_complete(asyncio.open_connection('127.0.0.1', 8888))
    except Exception as e:
        log.warning("admission control nonfunctional, unable to connect to server: %s", e)
        traceback.print_exc(file=sys.stdout)
        traceback.print_exc(file=sys.stderr)
        quit(1)
    evloop.run_until_complete(acquire_cores_lambda(reader, writer, number_cores, rpc))
    evloop.stop()
    evloop.close()


def relinquish_cores(number_cores):
    evloop = asyncio.new_event_loop()
    try:
        reader, writer = evloop.run_until_complete(asyncio.open_connection('127.0.0.1', 8888))
    except Exception as e:
        log.warning("admission control nonfunctional, unable to connect to server: %s", e)
        traceback.print_exc(file=sys.stdout)
        traceback.print_exc(file=sys.stderr)
        quit(1)
    evloop.run_until_complete(relinquish_cores_lambda(reader, writer, number_cores))
    evloop.stop()
    evloop.close()



class AuthServiceProxyWrapper(object):
    """
    An object that wraps AuthServiceProxy to record specific RPC calls.

    """
    def __init__(self, auth_service_proxy_instance, coverage_logfile=None):
        """
        Kwargs:
            auth_service_proxy_instance (AuthServiceProxy): the instance
                being wrapped.
            coverage_logfile (str): if specified, write each service_name
                out to a file when called.

        """
        self.auth_service_proxy_instance = auth_service_proxy_instance
        self.coverage_logfile = coverage_logfile

    def __getattr__(self, *args, **kwargs):
        return_val = self.auth_service_proxy_instance.__getattr__(
            *args, **kwargs)

        return AuthServiceProxyWrapper(return_val, self.coverage_logfile)

    def __call__(self, *args, **kwargs):
        """
        Delegates to AuthServiceProxy, then writes the particular RPC method
        called to a file.

        """
        rpc_method = self.auth_service_proxy_instance._service_name

        async_calls = ["z_sendmany", "z_mergetoaddress", "z_shieldcoinbase", "saplingmigration"]
        sync_calls = ["generate", "zcrawjoinsplit"]

        if (rpc_method in async_calls):
            log.warning("rpc method is %s", self.auth_service_proxy_instance._service_name)
            acquire_cores(16, rpc_method)

        if (rpc_method in sync_calls):
            log.warning("rpc method is %s", self.auth_service_proxy_instance._service_name)
            acquire_cores(16, rpc_method)

        try:
            return_val = self.auth_service_proxy_instance.__call__(*args, **kwargs)
        except Exception as e:
            if (rpc_method in async_calls):
                relinquish_cores(16)
            raise

        if (rpc_method in ["z_getoperationresult"] and len(return_val) > 0): # FIXME MAYBE? add a condition that there's at least one argument to z_getoperationresult?
            log.warning("OPERATION COMPLETED! WHEE! %s" % len(return_val))
            log.warning("rpc method is %s", self.auth_service_proxy_instance._service_name)
            relinquish_cores(16)

        if (rpc_method in sync_calls):
            relinquish_cores(16)

        if self.coverage_logfile:
            with open(self.coverage_logfile, 'a+', encoding='utf8') as f:
                f.write("%s\n" % rpc_method)

        return return_val

    @property
    def url(self):
        return self.auth_service_proxy_instance.url


def get_filename(dirname, n_node):
    """
    Get a filename unique to the test process ID and node.

    This file will contain a list of RPC commands covered.
    """
    pid = str(os.getpid())
    return os.path.join(
        dirname, "coverage.pid%s.node%s.txt" % (pid, str(n_node)))


def write_all_rpc_commands(dirname, node):
    """
    Write out a list of all RPC functions available in `bitcoin-cli` for
    coverage comparison. This will only happen once per coverage
    directory.

    Args:
        dirname (str): temporary test dir
        node (AuthServiceProxy): client

    Returns:
        bool. if the RPC interface file was written.

    """
    filename = os.path.join(dirname, REFERENCE_FILENAME)

    if os.path.isfile(filename):
        return False

    help_output = node.help().split('\n')
    commands = set()

    for line in help_output:
        line = line.strip()

        # Ignore blanks and headers
        if line and not line.startswith('='):
            commands.add("%s\n" % line.split()[0])

    with open(filename, 'w', encoding='utf8') as f:
        f.writelines(list(commands))

    return True

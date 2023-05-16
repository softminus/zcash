#!/usr/bin/env python3
#
# WARNING: THIS IS NOT THE ORIGINAL SMOKE_TESTS.PY
# This is a hastily-written modification that tests all possible 1-input 1-output z_sendmany transactions
# It operates by creating a single chain of transactions, where each transaction's input is the output of the previous transaction
# this is incredibly inefficient
# i call it T H E  S P I N N E R
#
# Execute the standard smoke tests for Zcash releases.
#
# Usage:
#
# ZCASHD=./src/zcashd ZCASHCLI=./src/zcash-cli ./qa/zcash/smoke_tests.py --wallet=wallet.smoketest.dat "$HOME/.zcash"
# 
# ZCASHD=./src/zcashd ZCASHCLI=./src/zcash-cli ./qa/zcash/smoke_tests.py --wallet=wallet.smoketest.dat "$HOME/.zcash" --automate --use-faucet
#

import argparse
import datetime
import os
import requests
import subprocess
import sys
import time
import traceback

from decimal import Decimal
from slickrpc import Proxy
from slickrpc.exc import RpcException

DEFAULT_FEE = Decimal('0.00001')
URL_FAUCET_DONATION = 'https://faucet.testnet.z.cash/donations'
URL_FAUCET_TAP = 'https://faucet.testnet.z.cash/'

#
# Smoke test definitions
#

# (case, expected_mainnet, expected_testnet)
SMOKE_TESTS = [
    # zcashd start/stop/restart flows
    ('1a', True, True), # zcashd start
    ('1b', True, True), # Graceful zcashd stop
    ('1c', True, True), # Ungraceful zcashd stop
    ('1d', True, True), # zcashd start; graceful zcashd stop; zcashd start
    ('1e', True, True), # zcashd start; ungraceful zcashd stop; zcashd start
    # Control
    ('2a', True, True), # Run getinfo
    ('2b', True, True), # Run help
    # Address generation
    #('3a', True, True), # Generate a Sprout z-addr
    #('3b', True, True), # Generate multiple Sprout z-addrs
    ('3c', True, True), # Generate a t-addr
    ('3d', True, True), # Generate multiple t-addrs
    ('3e', True, True), # Generate a Sapling z-addr
    ('3f', True, True), # Generate multiple Sapling z-addrs
    # Transactions
    #('4a', True,  True ), # Send funds from Sprout z-addr to same Sprout z-addr
    #('4b', True,  True ), # Send funds from Sprout z-addr to a different Sprout z-addr
    #('4c', True,  True ), # Send funds from Sprout z-addr to a t-addr
    #('4d', False,  False ), # Send funds from t-addr to Sprout z-addr(expected fail as of Canopy)
    ('4e', True,  True ), # Send funds from t-addr to t-addr
    ('4f', True,  True ), # Send funds from t-addr to Sapling z-addr
    ('4g', True,  True ), # Send funds from Sapling z-addr to same Sapling z-addr
    ('4h', True,  True ), # Send funds from Sapling z-addr to a different Sapling z-addr
    ('4i', True,  True ), # Send funds from Sapling z-addr to a t-addr
    #('4j', False, False), # Send funds from Sprout z-addr to Sapling z-addr
    #('4k', True,  True ), # Send funds from Sprout z-addr to multiple Sprout z-addrs
    #('4l', True,  True ), # Send funds from Sprout z-addr to multiple t-addrs
    #('4m', True,  True ), # Send funds from Sprout z-addr to t-addr and Sprout z-addrs
    #('4n', False, False), # Send funds from Sprout z-addr to t-addr and Sapling z-addr
    #('4o', False, False), # Send funds from Sprout z-addr to multiple Sapling z-addrs
    ('4p', True,  True ), # Send funds from t-addr to multiple t-addrs
    #('4q', False,  False ), # Send funds from t-addr to multiple Sprout z-addrs(expected fail as of Canopy)
    ('4r', True,  True ), # Send funds from t-addr to multiple Sapling z-addrs
    #('4s', False, False), # Send funds from t-addr to Sprout z-addr and Sapling z-addr
    ('4t', True,  True ), # Send funds from Sapling z-addr to multiple Sapling z-addrs
    #('4u', False, False), # Send funds from Sapling z-addr to multiple Sprout z-addrs
    ('4v', True,  True ), # Send funds from Sapling z-addr to multiple t-addrs
    ('4w', True,  True ), # Send funds from Sapling z-addr to t-addr and Sapling z-addr
    #('4x', False, False), # Send funds from Sapling z-addr to Sapling z-addr and Sprout z-addr
    #('4y', False,  False ), # Send funds from t-addr to Sprout z-addr using z_mergetoaddress(expected fail as of Canopy)
    #('4z', False,  False ), # Send funds from 2 different t-addrs to Sprout z-addr using z_mergetoaddress(expected fail as of Canopy)
    #('4aa', False, False), # Send funds from the same 2 t-addrs to Sprout z-addr using z_mergetoaddress
    ('4bb', True,  True ), # Send funds from 2 different t-addrs to Sapling z-addr using z_mergetoaddress
    ('4cc', True,  True ), # Send funds from t-addr to Sapling z-addr using z_mergetoaddress
    #('4dd', False,  False ), # Send funds from t-addr and Sprout z-addr to Sprout z-addr using z_mergetoaddress(expected fail as of Canopy)
    ('4ee', True,  True ), # Send funds from t-addr and Sapling z-addr to Sapling z-addr using z_mergetoaddress
    #('4ff', True,  True ), # Send funds from Sprout z-addr and Sprout z-addr to Sprout z-addr using z_mergetoaddress
    ('4gg', True,  True ), # Send funds from  Sapling z-addr and Sapling z-addr to Sapling z-addr using z_mergetoaddress
    # Wallet
    ('5a', True, True), # After generating multiple z-addrs, run z_listaddresses
    #('5b', True, True), # Run z_validateaddress with a Sprout z-addr
    ('5c', True, True), # Run z_validateaddress with a Sapling z-addr
    ('5d', True, True), # After a transaction, run z_listunspent
    ('5e', True, True), # After a transaction, run z_listreceivedbyaddress
    ('5f', True, True), # After a transaction, run z_getbalance
    ('5g', True, True), # After a transaction, run z_gettotalbalance
    ('5h', True, True), # Run z_exportkey using a Sprout z-addr
    ('5i', True, True), # Run z_importkey using the zkey from a Sprout z-addr
    ('5j', True, True), # Run z_exportkey using a Sapling z-addr
    ('5k', True, True), # Run z_importkey using the zkey from a Sapling z-addr
    ('5l', True, True), # Run z_exportwallet
    ('5m', True, True), # Run z_importwallet
    ('5n', True, True), # Run z_shieldcoinbase
    ('5o', True, True), # Run getwalletinfo
    # Network
    ('6a', True, True), # Run getpeerinfo
    ('6b', True, True), # Run getnetworkinfo
    ('6c', True, False), # Run getdeprecationinfo
    ('6d', True, True), # Run getconnectioncount
    ('6e', True, True), # Run getaddednodeinfo
    # Mining
    ('7a', True, True), # Run getblocksubsidy
    ('7b', True, True), # Run getblocktemplate
    ('7c', True, True), # Run getmininginfo
    ('7d', True, True), # Run getnetworkhashps
    ('7e', True, True), # Run getnetworksolps
]

TIME_STARTED = datetime.datetime.now()

#
# Test helpers
#

def run_cmd(results, case, zcash, name, args=[]):
    print('----- %s -----' % (datetime.datetime.now() - TIME_STARTED))
    print('%s $ zcash-cli %s %s' % (
        case.ljust(3),
        name,
        ' '.join([str(arg) for arg in args],
    )))
    try:
        res = zcash.__getattr__(name)(*args)
        print(res)
        print()
        if results is not None and len(case) > 0:
            results[case] = True
        return res
    except RpcException as e:
        print('ERROR: %s' % str(e))
        if results is not None and len(case) > 0:
            results[case] = False
        return None

def wait_for_balance(zcash, zaddr, expected=None, minconf=1):
    if (minconf == 1):
        print('Waiting for funds to %s...' % zaddr)
    else:
        print('Waiting for funds to %s to receive %d confirmations...' % (zaddr, minconf))
    unconfirmed_balance = Decimal(zcash.z_getbalance(zaddr, 0)).quantize(Decimal('1.00000000'))
    print('Expecting: %s; Unconfirmed Balance: %s' % (expected, unconfirmed_balance))
    if expected is not None and unconfirmed_balance != expected:
        print('WARNING: Unconfirmed balance does not match expected balance')

    # Default timeout is 15 minutes
    ttl = 900
    while True:
        balance = Decimal(zcash.z_getbalance(zaddr, minconf)).quantize(Decimal('1.00000000'))
        if (expected is not None and balance == unconfirmed_balance) or (expected is None and balance > 0):
            print('Received %s' % balance)
            return balance

        time.sleep(1)
        ttl -= 1
        if ttl == 0:
            if zcash.automated:
                # Reset timeout
                ttl = 300
            else:
                # Ask user if they want to keep waiting
                print()
                print('Balance: %s Expected: %s' % (balance, expected))
                ret = input('Do you wish to continue waiting? (Y/n) ')
                if ret.lower() == 'n':
                    print('Address contained %s at timeout' % balance)
                    return balance
                else:
                    # Wait another 5 minutes before asking again
                    ttl = 300

def wait_and_check_balance(results, case, zcash, addr, expected):
    #Wait for async call to finish and persist completely to caller
    time.sleep(5)
    balance = wait_for_balance(zcash, addr, expected)
    if balance != expected and results is not None and len(case) > 0:
        results[case] = False
    return balance

def wait_for_txid_operation(zcash, opid, timeout=300):
    print('Waiting for async operation %s' % opid)
    result = None
    for _ in iter(range(timeout)):
        results = zcash.z_getoperationresult([opid])
        if len(results) > 0:
            result = results[0]
            break
        time.sleep(1)

    status = result['status']
    if status == 'failed':
        print('Operation failed')
        print(result['error']['message'])
        return None
    elif status == 'success':
        txid = result['result']['txid']
        print('txid: %s' % txid)
        return txid

def async_txid_cmd(results, case, zcash, name, args=[]):
    opid = run_cmd(results, case, zcash, name, args)
    # Some async commands return a dictionary containing the opid
    if isinstance(opid, dict):
        opid = opid['opid']
    if opid is None:
        if results is not None and len(case) > 0:
            results[case] = False
        return None

    txid = wait_for_txid_operation(zcash, opid)
    if txid is None:
        if results is not None and len(case) > 0:
            results[case] = False
    return txid

def z_sendmany(results, case, zcash, from_addr, recipients, privacy_policy):
    return async_txid_cmd(results, case, zcash, 'z_sendmany', [
        from_addr,
        [{
            'address': to_addr,
            'amount': amount,
        } for (to_addr, amount) in recipients],
        1, # minconf
        0.00001, # fee
        privacy_policy
    ])

def check_z_sendmany(results, case, zcash, from_addr, recipients, privacy_policy):
    txid = z_sendmany(results, case, zcash, from_addr, recipients, privacy_policy)
    if txid is None:
        return [Decimal('0')]
    return [wait_and_check_balance(results, case, zcash, to_addr, amount) for (to_addr, amount) in recipients]

def check_z_sendmany_parallel(results, zcash, runs):
    # First attempt to create all the transactions
    txids = [(run, z_sendmany(results, run[0], zcash, run[1], run[2], run[3])) for run in runs]
    # Then wait for balance updates caused by successful transactions
    return [
        wait_and_check_balance(results, run[0], zcash, to_addr, amount) if txid is not None else Decimal('0')
        for (run, txid) in txids
        for (to_addr, amount) in run[2]]

def z_mergetoaddress(results, case, zcash, from_addrs, to_addr, privacy_policy):
    for addr in from_addrs:
        balance = Decimal(zcash.z_getbalance(addr, 0)).quantize(Decimal('1.00000000'))
        if balance > 0:
            wait_for_balance(zcash, addr, balance, minconf=4)
    return async_txid_cmd(results, case, zcash, 'z_mergetoaddress', [from_addrs, to_addr, DEFAULT_FEE, 50, 20, None, privacy_policy])

def check_z_mergetoaddress(results, case, zcash, from_addrs, to_addr, amount, privacy_policy):
    txid = z_mergetoaddress(results, case, zcash, from_addrs, to_addr, privacy_policy)
    if txid is None:
        return Decimal('0')
    return wait_and_check_balance(results, case, zcash, to_addr, amount)

def check_z_mergetoaddress_parallel(results, zcash, runs):
    # First attempt to create all the transactions
    txids = [(run, z_mergetoaddress(results, run[0], zcash, run[1], run[2], run[4])) for run in runs]
    # Then wait for balance updates caused by successful transactions
    return [
        wait_and_check_balance(results, run[0], zcash, run[2], run[3]) if txid is not None else Decimal('0')
        for (run, txid) in txids]

def tap_zfaucet(addr):
    with requests.Session() as session:
        # Get token to request TAZ from faucet with a given zcash address
        response = session.get(URL_FAUCET_TAP)
        if response.status_code != 200:
            print("Error establishing session at:", URL_FAUCET_TAP)
            os.sys.exit(1)
        csrftoken = response.cookies['csrftoken']

        # Request TAZ from the faucet
        data_params = dict(csrfmiddlewaretoken=csrftoken, address=addr)
        response2 = session.post(URL_FAUCET_TAP, data=data_params, headers=dict(Referer=URL_FAUCET_TAP))
        if response2.status_code != 200:
            print("Error tapping faucet at:", URL_FAUCET_TAP)
            os.sys.exit(1)

def get_zfaucet_addrs():
    with requests.Session() as session:
        response = session.get(URL_FAUCET_DONATION)
        if response.status_code != 200:
            print("Error establishing session at:", URL_FAUCET_DONATION)
            os.sys.exit(1)
        data = response.json()
    return data

def get_zfaucet_taddr():
    return get_zfaucet_addrs()["t_address"]

def get_zfaucet_zsapaddr():
    # At the time of writing this, it appears these(keys) are backwards
    return get_zfaucet_addrs()["z_address_legacy"]

def get_zfaucet_zsproutaddr():
    # At the time of writing this, it appears these(keys) are backwards
    return get_zfaucet_addrs()["z_address_sapling"]


#
# Spinner logic
#

address_types = [
    ["p2pkh"], # t-addr
    ["non_ua_sapling"], # z-addr
    ["sapling"], # UA
    ["orchard"], # UA
    ["sapling", "orchard"], # UA
    ["p2pkh", "sapling"], # UA
    ["p2pkh", "orchard"], # UA
    ["p2pkh", "sapling", "orchard"] # UA
]

def generate_ua_address(results, case, zcash, account_number, address_types):
    ret = run_cmd(results, case, zcash, 'z_getaddressforaccount', [account_number, address_types])
    print("created address:", ret['address'])
    return ret['address']

def generate_address_ondemand(results, case, zcash, account_number, address_type):
    if address_type == ["p2pkh"]:
        return run_cmd(results, case, zcash, 'getnewaddress')
    elif address_type == ["non_ua_sapling"]:
        return run_cmd(results, case, zcash, 'z_getnewaddress', ['sapling'])
    else:
        return generate_ua_address(results, case, zcash, account_number, address_type)


def create_pairs(address_types, sequence):
    if len(sequence) == len(address_types) * len(address_types):
        return sequence

    last_type = sequence[-1][1]
    for address_type in address_types:
        if (last_type, address_type) not in sequence:
            next_sequence = sequence.copy()
            next_sequence.append((last_type, address_type))
            result = create_pairs(address_types, next_sequence)
            if result:
                return result

    return None



def run_transactions(results, case, zcash, account_number, pairs_sequence, starting_taddr, initial_balance):
    address_mapping = {("p2pkh",): starting_taddr}
    current_balance = initial_balance

    for from_type, to_type in pairs_sequence:
        print("ROUND OF THE SPINNER {} {}", from_type, to_type)
        # Create new addresses if not already created
        from_type_tuple = tuple(from_type)
        to_type_tuple = tuple(to_type)

        if from_type_tuple not in address_mapping:
            address_mapping[from_type_tuple] = generate_address_ondemand(results, case, zcash, account_number, from_type)
        if to_type_tuple not in address_mapping:
            address_mapping[to_type_tuple] = generate_address_ondemand(results, case, zcash, account_number, to_type)

        from_addr = address_mapping[from_type_tuple]
        to_addr = address_mapping[to_type_tuple]
        print("FROM {} TO {}", from_addr, to_addr)

        # Calculate the amount to send after accounting for the default fee
        send_amount = current_balance - DEFAULT_FEE
        if send_amount < 0:
            print("Insufficient funds.")
            return
        print("SENDING {}", send_amount)

        # Perform the transaction
        recipients = [( to_addr, send_amount)]
        print("SENDMANY {}", recipients)
        z_sendmany(results, case, zcash, from_addr, recipients, "NoPrivacy")
        print("SENDMANY DONE!")
        # Update the balance
        current_balance -= DEFAULT_FEE

        # Verify balance
        success = wait_and_check_balance(results, case, zcash, to_addr, send_amount)
        if not success:
            print(f"Transaction FAILED FAILED FAIIIILED : {from_type} -> {to_type}")
        else:
            print(f"Transaction succeeded: {from_type} -> {to_type}")

    # Verify final balance
    if not wait_and_check_balance(results, case, zcash, starting_taddr, current_balance):
        print("Final balance check failed.")
    else:
        print("All transactions completed successfully.")


#
# Test runners
#


def simple_commands(zcash):
    results = {}
    run_cmd(results, '2a', zcash, 'getinfo'),
    run_cmd(results, '2b', zcash, 'help'),
    run_cmd(results, '5o', zcash, 'getwalletinfo'),
    run_cmd(results, '6a', zcash, 'getpeerinfo'),
    run_cmd(results, '6b', zcash, 'getnetworkinfo'),
    run_cmd(results, '6c', zcash, 'getdeprecationinfo'),
    run_cmd(results, '6d', zcash, 'getconnectioncount'),
    run_cmd(results, '6e', zcash, 'getaddednodeinfo', [False]),
    run_cmd(results, '7a', zcash, 'getblocksubsidy'),
    run_cmd(results, '7c', zcash, 'getmininginfo'),
    run_cmd(results, '7d', zcash, 'getnetworkhashps'),
    run_cmd(results, '7e', zcash, 'getnetworksolps'),
    return results

def transaction_chain(zcash):
    results = {}

    # Generate the various addresses we will use
    taddr_1 = run_cmd(results, '3c', zcash, 'getnewaddress')

    account_number  = run_cmd(results, 'X00', zcash, 'z_getnewaccount')["account"]
    print("account number:", account_number)
    # Set up beginning and end of the chain
    print('#')
    print('# Initialising transaction chain')
    print('#')
    print()
    # if zcash.use_faucet:
    #     print('Tapping the testnet faucet for testing funds...')
    #     chain_end = get_zfaucet_taddr()
    #     tap_zfaucet(taddr_1)
    #     print('Done! Leftover funds will be sent back to the faucet.')
    # else:
    #     chain_end = input('Type or paste transparent address where leftover funds should be sent: ')
    #     if not zcash.validateaddress(chain_end)['isvalid']:
    #         print('Invalid transparent address')
    #         return results

    # print()
    print()
    print('Please send at least 0.01 ZEC/TAZ to the following address:')
    print(taddr_1)
    print()
    input('Press Enter once the funds have been sent.')
    # Wait to receive starting balance
    taddr_balance = wait_for_balance(zcash, taddr_1)
    starting_balance = taddr_balance

    #
    # Start the transaction chain!
    #
    print()
    print('#')
    print('# Starting The Spinner')
    print('#')
    print()
    try:
        pairs_sequence = create_pairs(address_types, [(address_types[0], address_types[0])])
        run_transactions(results, "X01", zcash, account_number, pairs_sequence, taddr_1, starting_balance)


    except Exception as e:
        print('Error: %s' % e)
        traceback.print_exc()
    return results


#
# Test stages
#

STAGES = [
    'simple-commands',
    'transaction-chain'
]

STAGE_COMMANDS = {
    'simple-commands': simple_commands,
    'transaction-chain': transaction_chain,
}

def run_stage(stage, zcash):
    print('Running stage %s' % stage)
    print('=' * (len(stage) + 14))
    print()

    cmd = STAGE_COMMANDS[stage]
    if cmd is not None:
        ret = cmd(zcash)
    else:
        print('WARNING: stage not yet implemented, skipping')
        ret = {}

    print()
    print('-' * (len(stage) + 15))
    print('Finished stage %s' % stage)
    print()

    return ret


#
# Zcash wrapper
#

class ZcashNode(object):
    def __init__(self, args, zcashd=None, zcash_cli=None):
        if zcashd is None:
            zcashd = os.getenv('ZCASHD', 'zcashd')
        if zcash_cli is None:
            zcash_cli = os.getenv('ZCASHCLI', 'zcash-cli')

        self.__datadir = args.datadir
        self.__wallet = args.wallet
        self.__testnet = not args.mainnet
        self.__zcashd = zcashd
        self.__zcash_cli = zcash_cli
        self.__process = None
        self.__proxy = None

        self.automated = args.automate
        self.use_faucet = args.faucet

    def start(self, extra_args=None, timewait=None):
        if self.__proxy is not None:
            raise RuntimeError('Already started')

        rpcuser = 'st'
        rpcpassword = 'st'

        args = [
            self.__zcashd,
            '-datadir=%s' % self.__datadir,
            '-wallet=%s' % self.__wallet,
            '-rpcuser=%s' % rpcuser,
            '-rpcpassword=%s' % rpcpassword,
            '-showmetrics=0',
            '-experimentalfeatures',
            '-zmergetoaddress',
            '-walletrequirebackup=false',
            '-allowdeprecated=getnewaddress',
            '-allowdeprecated=z_getnewaddress',
            '-allowdeprecated=z_listaddresses'
        ]
        if self.__testnet:
            args.append('-testnet=1')
        if extra_args is not None:
            args.extend(extra_args)

        self.__process = subprocess.Popen(args)

        cli_args = [
            self.__zcash_cli,
            '-datadir=%s' % self.__datadir,
            '-rpcuser=%s' % rpcuser,
            '-rpcpassword=%s' % rpcpassword,
            '-rpcwait',
        ]
        if self.__testnet:
            cli_args.append('-testnet=1')
        cli_args.append('getblockcount')

        devnull = open('/dev/null', 'w+', encoding='utf8')
        if os.getenv('PYTHON_DEBUG', ''):
            print('start_node: zcashd started, calling zcash-cli -rpcwait getblockcount')
        subprocess.check_call(cli_args, stdout=devnull)
        if os.getenv('PYTHON_DEBUG', ''):
            print('start_node: calling zcash-cli -rpcwait getblockcount returned')
        devnull.close()

        rpcuserpass = '%s:%s' % (rpcuser, rpcpassword)
        rpchost = '127.0.0.1'
        rpcport = 18232 if self.__testnet else 8232

        url = 'http://%s@%s:%d' % (rpcuserpass, rpchost, rpcport)
        if timewait is not None:
            self.__proxy = Proxy(url, timeout=timewait)
        else:
            self.__proxy = Proxy(url)

    def stop(self):
        if self.__proxy is None:
            raise RuntimeError('Not running')

        self.__proxy.stop()
        self.__process.wait()
        self.__proxy = None
        self.__process = None

    def __getattr__(self, name):
        if self.__proxy is None:
            raise RuntimeError('Not running')

        return self.__proxy.__getattr__(name)


#
# Test driver
#

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--automate', action='store_true', help='Run the smoke tests without a user present')
    parser.add_argument('--list-stages', dest='list', action='store_true')
    parser.add_argument('--mainnet', action='store_true', help='Use mainnet instead of testnet')
    parser.add_argument('--use-faucet', dest='faucet', action='store_true', help='Use testnet faucet as source of funds')
    parser.add_argument('--wallet', default='wallet.dat', help='Wallet file to use (within data directory)')
    parser.add_argument('datadir', help='Data directory to use for smoke testing', default=None)
    parser.add_argument('stage', nargs='*', default=STAGES, help='One of %s' % STAGES)
    args = parser.parse_args()

    # Check for list
    if args.list:
        for s in STAGES:
            print(s)
        sys.exit(0)

    # Check validity of stages
    for s in args.stage:
        if s not in STAGES:
            print("Invalid stage '%s' (choose from %s)" % (s, STAGES))
            sys.exit(1)

    # Don't allow using the default wallet.dat in mainnet mode
    if args.mainnet and args.wallet == 'wallet.dat':
        print('Cannot use wallet.dat as wallet file when running mainnet tests. Keep your funds safe!')
        sys.exit(1)

    # Testnet faucet cannot be used in mainnet mode
    if args.mainnet and args.faucet:
        print('Cannot use testnet faucet when running mainnet tests.')
        sys.exit(1)

    # Enforce correctly-configured automatic mode
    if args.automate:
        if args.mainnet:
            print('Cannot yet automate mainnet tests.')
            sys.exit(1)
        if not args.faucet:
            print('--automate requires --use-faucet')
            sys.exit(1)

    # Start zcashd
    zcash = ZcashNode(args)
    print('Start time: %s' % TIME_STARTED)
    print('Starting zcashd...')
    zcash.start()
    print()

    # Run the stages
    results = {}
    for s in args.stage:
        results.update(run_stage(s, zcash))

    # Stop zcashd
    print('Stopping zcashd...')
    zcash.stop()

    passed = True
    print()
    print('========================')
    print('       Results')
    print('========================')
    print('Case | Expected | Actual')
    print('========================')
    for test_case in SMOKE_TESTS:
        case = test_case[0]
        expected = test_case[1 if args.mainnet else 2]
        if case in results:
            actual = results[case]
            actual_str = '%s%s' % (
                'Passed' if actual else 'Failed',
                '' if expected == actual else '!!!'
            )
            passed &= (expected == actual)
        else:
            actual_str = ' N/A'
        print('%s | %s | %s' % (
            case.ljust(4),
            ' Passed ' if expected else ' Failed ',
            actual_str
        ))

    if not passed:
        print()
        print("!!! One or more smoke test stages failed !!!")
        sys.exit(1)


if __name__ == '__main__':
    main()

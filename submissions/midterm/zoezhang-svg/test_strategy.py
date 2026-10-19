"""Offline risk tests; no RPC and no signing."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch, MagicMock

stub = types.ModuleType('chain')
for name in ('ADDR', 'at', 'erc20', 'acct_of', 'send', 'w3', 'CHAIN_ID'):
    setattr(stub, name, {} if name == 'ADDR' else None)
spec = importlib.util.spec_from_file_location('tested_strategy', Path(__file__).with_name('strategy.py'))
bot = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'chain': stub}):
    spec.loader.exec_module(bot)
W = bot.WAD

class RiskTests(unittest.TestCase):
    def venues(self, **changes):
        return [dict(name='LendA', apr=W//5, util=W//2, cash=10_000*W, shares=0, **changes)] if not changes else [{**self.venues()[0], **changes}]

    def test_normal(self):
        s = bot.choose(1000*W, self.venues())
        self.assertEqual(s['amount'], 100*W)
        self.assertGreaterEqual(s['expected_30d'], bot.MIN_RETURN)

    def test_no_yield(self):
        self.assertIsNone(bot.choose(1000*W, self.venues(apr=0)))

    def test_invalid_data(self):
        for changes in ({'cash': -1}, {'util': -1}, {'apr': 2*W}, {'util': W}):
            self.assertIsNone(bot.choose(1000*W, self.venues(**changes)))

    def test_low_balance(self):
        self.assertIsNone(bot.choose(9*W, self.venues()))

    def test_existing_position(self):
        self.assertIsNone(bot.choose(1000*W, self.venues(shares=1)))

    def test_caps(self):
        self.assertEqual(bot.choose(10_000*W, self.venues())['amount'], bot.CAP)
        self.assertEqual(bot.choose(500*W, self.venues())['amount'], 50*W)
        self.assertEqual(bot.choose(1000*W, self.venues(cash=200*W))['amount'], 20*W)

    def test_venue_selection(self):
        venues = self.venues() + [{**self.venues()[0], 'name':'LendB', 'apr':W//2}]
        self.assertEqual(bot.choose(1000*W, venues)['venue'], 'LendB')

    def test_missing_wallet(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertFalse(bot.scan()['hit'])

    def test_no_authorization(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(RuntimeError):
                bot.fire({'hit':True})

    def test_scan_fails_closed(self):
        with patch.object(bot, 'wallet', side_effect=ValueError('sensitive')):
            self.assertEqual(bot.scan()['line'], 'unavailable data/configuration (ValueError)')

class ExecutionTests(unittest.TestCase):
    def test_stale_scan_stops_before_send(self):
        with patch.dict('os.environ', {'AGENT_KEY':'test-only', 'CONFIRM_BASE_SEPOLIA':'YES'}), patch.object(bot, 'scan', return_value={'hit':False}), patch.object(bot, 'send') as send:
            with self.assertRaises(RuntimeError):
                bot.fire({'hit':True})
            send.assert_not_called()

    def test_failed_approval_never_supplies(self):
        fresh = dict(hit=True, wallet='public-wallet', venue='LendA', amount=100*W)
        client = MagicMock()
        client.eth.gas_price = 1
        client.eth.get_balance.return_value = W
        client.eth.get_code.return_value = b'code'
        token, pool = MagicMock(), MagicMock()
        token.functions.allowance.return_value.call.return_value = 0
        with patch.dict('os.environ', {'AGENT_KEY':'test-only', 'CONFIRM_BASE_SEPOLIA':'YES'}), patch.object(bot, 'scan', return_value=fresh), patch.object(bot, 'ADDR', {'LendA':'pool', 'tUSDC':'token'}), patch.object(bot, 'w3', client), patch.object(bot, 'erc20', return_value=token), patch.object(bot, 'at', return_value=pool), patch.object(bot, 'send', side_effect=RuntimeError('failed')) as send:
            with self.assertRaises(RuntimeError):
                bot.fire(fresh)
            send.assert_called_once()
            self.assertEqual(send.call_args.kwargs['retries'], 1)
            self.assertEqual(send.call_args.kwargs['key'], 'test-only')
            token.functions.approve.assert_called_once_with('pool', 100*W)
            pool.functions.supply.assert_not_called()

if __name__ == '__main__':
    unittest.main()

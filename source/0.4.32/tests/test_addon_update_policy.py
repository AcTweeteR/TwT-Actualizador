import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources/lib'))
from addon_update_policy import ensure_notify_only


class UpdatePolicyTests(unittest.TestCase):
    def setUp(self):
        self.value=0
        self.methods=[]
        self.reject=False

    def rpc(self, request):
        req=json.loads(request);self.methods.append(req['method'])
        if req['method']=='Settings.GetSettingValue':result={'value':self.value}
        else:
            result=not self.reject
            if result:self.value=req['params']['value']
        return json.dumps({'jsonrpc':'2.0','id':req['id'],'result':result})

    def test_sets_notify_only_and_verifies(self):
        self.assertEqual(ensure_notify_only(self.rpc),'PROTECTED')
        self.assertEqual(self.value,1)
        self.assertEqual(self.methods,['Settings.GetSettingValue','Settings.SetSettingValue','Settings.GetSettingValue'])

    def test_idempotent(self):
        self.value=1
        self.assertEqual(ensure_notify_only(self.rpc),'ALREADY_PROTECTED')
        self.assertEqual(self.methods,['Settings.GetSettingValue'])

    def test_rejected_change_is_not_claimed_success(self):
        self.reject=True
        with self.assertRaises(RuntimeError):ensure_notify_only(self.rpc)
        self.assertEqual(self.value,0)

    def test_invalid_reply_fails_closed(self):
        with self.assertRaises((RuntimeError,ValueError)):
            ensure_notify_only(lambda _: '{"error":{"code":-1}}')

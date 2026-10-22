import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources/lib/trakt_resume_bridge.py'
spec=importlib.util.spec_from_file_location('trakt_resume_bridge_test',path)
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)


class ResumeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.plan={'items':[{'provider_id':'12','position':600.0,'duration':2400.0}]}
        self.ref={'12':{'provider_id':'12','name':'Synthetic movie','url':'https://example.invalid/test.mp4'}}

    def test_verified_reference_stages_native_format_without_mutation(self):
        local={}
        result=bridge.stage_resume(self.plan,self.ref,local)
        self.assertEqual(result['added'],1)
        self.assertEqual(local,{})
        self.assertEqual(result['staged']['Synthetic movie||https://example.invalid/test.mp4']['position'],600)

    def test_no_reference_never_guesses_url(self):
        result=bridge.stage_resume(self.plan,{}, {})
        self.assertEqual(result['added'],0)
        self.assertEqual(result['deferred'],['12'])

    def test_existing_local_resume_is_not_overwritten(self):
        key='Synthetic movie||https://example.invalid/test.mp4'
        local={key:{'position':100}}
        result=bridge.stage_resume(self.plan,self.ref,local)
        self.assertEqual(result['added'],0)
        self.assertEqual(result['staged'][key]['position'],100)

    def test_invalid_and_near_end_progress_is_deferred(self):
        self.plan['items'][0]['position']=2399
        self.assertEqual(bridge.stage_resume(self.plan,self.ref,{})['added'],0)


if __name__=='__main__':unittest.main()

import io
import json
import os
import unittest
import urllib.error
from unittest.mock import Mock, patch
from adapters import GroqInference
from core import Support, Chunk

class GroqTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key(self):
        with self.assertRaises(ValueError): GroqInference()

    def response(self, content, reason='stop'):
        return io.BytesIO(json.dumps({'choices':[{'finish_reason':reason,'message':{'content':content}}]}).encode())

    @patch.dict(os.environ, {'GROQ_API_KEY':'test-placeholder-not-a-real-key'}, clear=True)
    @patch('urllib.request.build_opener')
    def test_contract(self, build):
        build.return_value.open.return_value = self.response('{"acao":"encaminhar","resposta":"Suporte","fontes":[]}')
        result=GroqInference().infer('system JSON','pergunta')
        self.assertEqual(result['acao'],'encaminhar')
        request=build.return_value.open.call_args.args[0]
        data=json.loads(request.data)
        self.assertEqual(request.full_url,'https://api.groq.com/openai/v1/chat/completions')
        self.assertEqual(data['model'],'openai/gpt-oss-20b')
        self.assertEqual(data['response_format'],{'type':'json_object'})
        self.assertEqual(data['messages'][0]['role'],'system')
        self.assertEqual(request.get_header('Authorization'),'Bearer test-placeholder-not-a-real-key')
        self.assertEqual(build.return_value.open.call_args.kwargs['timeout'],90)

    @patch.dict(os.environ, {'GROQ_API_KEY':'test-placeholder-not-a-real-key'}, clear=True)
    @patch('urllib.request.build_opener')
    def test_failures_escalate(self, build):
        docs=Mock(); docs.read.return_value=[Chunk('1','wifi','configurar wifi','https://docs.google.com/')]
        tickets=Mock(); support=Support(docs,GroqInference(),tickets)
        for code in (401,403,429,500):
            with self.subTest(code=code):
                build.return_value.open.side_effect=urllib.error.HTTPError('https://api.groq.com',code,'redacted',{},None)
                self.assertEqual(support.triage('wifi')['acao'],'encaminhar')
                tickets.append.assert_not_called()
        build.return_value.open.side_effect=TimeoutError()
        self.assertEqual(support.triage('wifi')['acao'],'encaminhar')

    @patch.dict(os.environ, {'GROQ_API_KEY':'test-placeholder-not-a-real-key'}, clear=True)
    @patch('urllib.request.build_opener')
    def test_invalid_and_truncated(self, build):
        for content, reason in [('not json','stop'),('{}','length')]:
            with self.subTest(reason=reason):
                build.return_value.open.return_value=self.response(content,reason)
                with self.assertRaises(ValueError): GroqInference().infer('JSON','wifi')

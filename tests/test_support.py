import unittest
from unittest.mock import Mock
from core import Chunk, Support, retrieve
from adapters import GoogleDocs, GoogleSheets, extract_text, tab_contents

class Tests(unittest.TestCase):
    def test_retrieve_ranking_and_stable_ties(self):
        chunks = [Chunk(str(i), '', text, '') for i, text in enumerate([
            'wifi', 'wifi rede', 'impressora', 'wifi', 'wifi', 'wifi',
        ])]
        self.assertEqual([c.id for c in retrieve('wifi rede', iter(chunks))], ['1', '0', '3', '4'])
        self.assertEqual(retrieve('como para', chunks), [])
        self.assertEqual(retrieve('servidor', chunks), [])

    def test_init_reads_only_header(self):
        from adapters import HEADERS
        api = Mock()
        values = api.spreadsheets().values()
        values.get().execute.return_value = {'values': [HEADERS]}
        GoogleSheets(api, 'id').init()
        values.get.assert_called_with(spreadsheetId='id', range="'Chamados'!A1:I1")
        values.update.assert_not_called()

    def setUp(self):
        self.docs, self.model, self.tickets = Mock(), Mock(), Mock()
        self.docs.read.return_value = [Chunk('wifi:0','Wi-Fi','Configurar wifi corporativo','https://docs.google.com/')]
        self.model.infer.return_value = {'acao':'orientar','resposta':'Consulte a rede corporativa.','fontes':['wifi:0']}
        self.app = Support(self.docs,self.model,self.tickets)
    def test_documented(self):
        self.assertEqual(self.app.triage('configurar wifi')['acao'],'orientar')
        self.tickets.append.assert_not_called()
    def test_unknown(self):
        self.assertEqual(self.app.triage('restaurar servidor')['acao'],'encaminhar')
        self.model.infer.assert_not_called()
    def test_docs_failure(self):
        self.docs.read.side_effect = RuntimeError('403 secret')
        r = self.app.triage('wifi')
        self.assertEqual(r['acao'],'encaminhar')
        self.assertNotIn('secret',str(r))
    def test_model_timeout(self):
        self.model.infer.side_effect = TimeoutError()
        self.assertEqual(self.app.triage('wifi')['acao'],'encaminhar')
    def test_invalid_output(self):
        for result in [None,{}, {'acao':'executar'}, {'acao':'orientar','resposta':'abc','fontes':[]}, {'acao':'orientar','resposta':'abc','fontes':['inventada']}]:
            with self.subTest(result=result):
                self.model.infer.return_value = result
                self.assertEqual(self.app.triage('wifi')['acao'],'encaminhar')
    def test_ticket(self):
        r = self.app.open_ticket('Ana','RH','wifi falha','Tentou reconectar','setor')
        self.assertTrue(r['registrado'])
        row = self.tickets.append.call_args.args[0]
        self.assertEqual(len(row),9)
        self.assertEqual(row[-2:],['Alta','Aberto'])
    def test_failed_write(self):
        self.tickets.append.side_effect = TimeoutError()
        r = self.app.open_ticket('Ana','RH','wifi falha')
        self.assertFalse(r['registrado'])
        self.assertIsNone(r['protocolo'])
        self.assertTrue(r['referencia_tentativa'].startswith('TI-'))
    def test_input(self):
        for question in ['', 'x'*4001]:
            with self.assertRaises(ValueError): self.app.triage(question)
        with self.assertRaises(ValueError): self.app.open_ticket('','RH','wifi')
        self.tickets.append.assert_not_called()
    def test_priority(self):
        self.app.open_ticket('Ana','RH','erro',impact='seguranca')
        self.assertEqual(self.tickets.append.call_args.args[0][-2],'Crítica')
    def test_append_raw(self):
        api = Mock()
        api.spreadsheets().values().append().execute.return_value = {'updates':{'updatedRows':1}}
        GoogleSheets(api,'id',"D'Água").append(['=1+1']*9)
        args = api.spreadsheets().values().append.call_args.kwargs
        self.assertEqual(args['valueInputOption'],'RAW')
        self.assertEqual(args['range'],"'D''Água'!A:I")
        self.assertEqual(args['body']['values'][0][0],'=1+1')
        api.spreadsheets().values().append().execute.assert_called_with(num_retries=0)
    def test_missing_confirmation(self):
        api = Mock()
        api.spreadsheets().values().append().execute.return_value = {}
        with self.assertRaises(RuntimeError): GoogleSheets(api,'id').append(['x']*9)
    def test_nested_docs(self):
        paragraph = {'paragraph':{'elements':[{'textRun':{'content':'wifi'}}]}}
        content = [{'table':{'tableRows':[{'tableCells':[{'content':[paragraph]}]}]}}]
        self.assertEqual(extract_text(content),'wifi')
        tabs = [{'documentTab':{'body':{'content':[paragraph]}},'childTabs':[{'documentTab':{'body':{'content':content}}}]}]
        self.assertEqual(len(list(tab_contents(tabs))),2)
    def test_docs_request_tabs(self):
        api=Mock()
        api.documents().get().execute.return_value={'title':'Manual','tabs':[{'documentTab':{'body':{'content':[{'paragraph':{'elements':[{'textRun':{'content':'wifi'}}]}}]}}}]}
        chunks=GoogleDocs(api,['doc1']).read()
        self.assertEqual(chunks[0].text,'wifi')
        api.documents().get.assert_called_with(documentId='doc1',includeTabsContent=True)

if __name__=='__main__': unittest.main()
